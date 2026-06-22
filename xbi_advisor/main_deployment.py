"""
Main advisory pipeline — orchestrates Typeform ingestion, rules engine, LLM scoring, and PDF
generation. Called by xbi_advisor_app.py on every webhook request.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from google.cloud import storage

from xbi_advisor.export_typeform_responses import process_typeform_responses
from xbi_advisor.generate_pdf import generate_pdf
from xbi_advisor.llm import (
    create_prompt,
    generate_llm_scores,
    response_from_openai,
)
from xbi_advisor.modules.config import get_final_output_dir, get_tmp_dir
from xbi_advisor.parser import get_flattened_content
from xbi_advisor.rules_engine import RulesEngine
from xbi_advisor.typeform_output import (
    TypeformClient,
    TypeformResponseFormatter,
    process_typeform_data,
)

# ----------------------------
# Logging setup
# ----------------------------
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ----------------------------
# Load environment variables
# ----------------------------
load_dotenv()

# ----------------------------
# Paths
# ----------------------------
ASSETS_DIR = Path("xbi_advisor/assets")
TEMPLATES_DIR = ASSETS_DIR / "templates"
TYPEFORM_OUTPUT_DIR = Path("xbi_advisor/typeform_output")
MANUAL_RESPONSE_FILE = Path("examples/manual_responses.json")
QUESTION_MAPPING_FILE = TEMPLATES_DIR / "question_mapping.json"
SCORES_TEMPLATE_FILE = TEMPLATES_DIR / "scores_template.md"
RECOMMENDATION_TEMPLATE_FILE = TEMPLATES_DIR / "recommendation_template.md"
RULES_FILE = ASSETS_DIR / "rules/rules.yaml"

# ----------------------------
# GCS config for loop prevention
# ----------------------------
LAST_ID_BUCKET = "xbi-advisor-bucket"
LAST_ID_FILE = "last_processed_id.txt"
PROCESSED_RESPONSES_FILE = "processed_responses.txt"


def generate_unique_pdf_path(
    recipient_email: str, response_id: str, organization: str = None
) -> tuple[str, Path]:
    """
    Generate a unique PDF path for each client response.

    Args:
        recipient_email: Email of the recipient
        response_id: TypeForm response ID/token
        organization: Organization name (optional)

    Returns:
        tuple: (gcs_path_string, local_path_object)
    """
    # Create a safe email hash for folder structure
    email_hash = hashlib.md5(recipient_email.lower().encode()).hexdigest()[:8]

    # Create timestamp for uniqueness
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create safe organization name
    safe_org = "unknown"
    if organization:
        safe_org = "".join(c for c in organization.lower() if c.isalnum() or c in "_-")[
            :20
        ]

    # Create folder structure: reports/{email_hash}/{org}/
    folder_structure = f"reports/{email_hash}/{safe_org}"

    # Create unique filename with response ID and timestamp
    filename = f"xbi_recommendation_{response_id}_{timestamp}.pdf"

    # Local path for generation (using FINAL_OUTPUT_DIR)
    final_output_dir = get_final_output_dir()
    local_path = final_output_dir / folder_structure / filename

    # GCS path for storage reference
    bucket_name = os.getenv("LAST_ID_BUCKET", LAST_ID_BUCKET)
    gcs_path = f"gs://{bucket_name}/{folder_structure}/{filename}"

    return gcs_path, local_path


def check_duplicate_response(response_id: str) -> bool:
    """
    Check if a response has already been processed.
    """
    try:
        client = storage.Client()
        bucket = client.bucket(LAST_ID_BUCKET)
        blob = bucket.blob(PROCESSED_RESPONSES_FILE)

        if blob.exists():
            processed_data = blob.download_as_text()
            processed_ids = [
                line.split(":")[0]
                for line in processed_data.splitlines()
                if ":" in line
            ]
            return response_id in processed_ids

        return False

    except Exception as e:
        logger.exception("Error checking duplicate: %s", e)
        return False


def record_processed_response(response_id: str, pdf_path: str):
    """
    Record that a response has been processed.
    """
    try:
        client = storage.Client()
        bucket = client.bucket(LAST_ID_BUCKET)
        blob = bucket.blob(PROCESSED_RESPONSES_FILE)

        # Get existing content
        existing_content = ""
        if blob.exists():
            existing_content = blob.download_as_text()

        # Add new entry
        new_entry = f"{response_id}:{pdf_path}\n"
        updated_content = existing_content + new_entry

        # Upload updated content
        blob.upload_from_string(updated_content)
        logger.info("Recorded processed response: %s", response_id)

    except Exception as e:
        logger.exception("Error recording processed response: %s", e)


def find_existing_pdf_for_response_id(
    response_id: str, email: str = None, organization: str = None
) -> str:
    """
    Find existing PDF for a given response ID.
    """
    try:
        client = storage.Client()
        bucket = client.bucket(LAST_ID_BUCKET)

        # First check processed responses file
        processed_blob = bucket.blob(PROCESSED_RESPONSES_FILE)
        if processed_blob.exists():
            processed_data = processed_blob.download_as_text()
            for line in processed_data.splitlines():
                if line.startswith(response_id + ":"):
                    pdf_path = line.split(":", 1)[1].strip()
                    logger.info("Found existing PDF for %s: %s", response_id, pdf_path)
                    return pdf_path

        # Alternative: search GCS bucket for files containing the response_id
        blobs = bucket.list_blobs(prefix="reports/")
        for blob in blobs:
            if response_id in blob.name and blob.name.endswith(".pdf"):
                logger.info("Found existing PDF in GCS: %s", blob.name)
                return f"gs://{LAST_ID_BUCKET}/{blob.name}"

        return None

    except Exception as e:
        logger.exception("Error finding existing PDF: %s", e)
        return None


def extract_email(payload: dict) -> str | None:
    """
    Extract email from webhook payload (supports multiple formats)
    """
    # Case 1: Direct from Power Automate
    if "recipient_email" in payload:
        return payload["recipient_email"]

    # Case 2: Nested Typeform structure
    form_response = payload.get("form_response", {})
    answers = form_response.get("answers", [])
    for answer in answers:
        if answer.get("type") == "email" and "email" in answer:
            return answer["email"]

    return None


def extract_organization(payload: dict) -> str | None:
    """
    Extract organization from webhook payload (supports multiple formats)
    """
    # Case 1: Direct from Power Automate
    if "organization" in payload:
        return payload["organization"]

    # Case 2: Nested Typeform structure
    form_response = payload.get("form_response", {})

    # Build a mapping of field ID to field title from the definition
    definition = form_response.get("definition", {})
    fields = definition.get("fields", [])
    field_id_to_title = {}

    for field in fields:
        field_id_to_title[field.get("id")] = field.get("title", "").lower()

    # Now check answers using the field ID to title mapping
    answers = form_response.get("answers", [])
    for answer in answers:
        if answer.get("type") == "text" and "field" in answer:
            field_id = answer["field"].get("id")
            field_title = field_id_to_title.get(field_id, "")

            # Check if this field is about organization
            if any(
                keyword in field_title
                for keyword in ["organization", "company", "business"]
            ):
                return answer.get("text")

    return None


def load_last_id_from_gcs():
    """
    Load the last processed ID from GCS (legacy function, kept for compatibility)
    """
    try:
        client = storage.Client()
        bucket = client.bucket(LAST_ID_BUCKET)
        blob = bucket.blob(LAST_ID_FILE)
        if blob.exists():
            return blob.download_as_text().strip()
    except Exception as e:
        logger.warning("Could not load last processed ID: %s", e)
    return None


def save_last_id_to_gcs(response_id):
    """
    Save the last processed ID to GCS (legacy function, kept for compatibility)
    """
    try:
        client = storage.Client()
        bucket = client.bucket(LAST_ID_BUCKET)
        blob = bucket.blob(LAST_ID_FILE)
        blob.upload_from_string(response_id)
    except Exception as e:
        logger.error("Could not save last processed ID: %s", e)


def trigger_power_automate_with_pdf(
    pdf_content: bytes, recipient_email: str, response_id: str, organization: str = None
):
    """
    Send PDF content directly to Power Automate with duplicate prevention
    """
    power_automate_url = os.getenv("POWER_AUTOMATE_WEBHOOK_URL")
    if not power_automate_url:
        logger.error("POWER_AUTOMATE_WEBHOOK_URL not configured")
        return False

    # Create a unique trigger ID to prevent duplicate Power Automate calls
    trigger_id = (
        f"{response_id}_{hashlib.md5(recipient_email.encode()).hexdigest()[:8]}"
    )

    # Check if we've already triggered Power Automate for this request
    if check_power_automate_triggered(trigger_id):
        logger.warning("Power Automate already triggered for %s, skipping", trigger_id)
        return True  # Return True since it was already triggered successfully

    # Convert PDF to base64 for transmission
    pdf_base64 = base64.b64encode(pdf_content).decode("utf-8")

    payload = {
        "recipient_email": recipient_email,
        "recipient_name": recipient_email.split("@")[0]
        if recipient_email
        else "Valued Client",
        "organization": organization or "XBI Advisory",
        "pdf_content_base64": pdf_base64,
        "pdf_filename": f"XBI_Recommendation_{response_id}.pdf",
        "is_duplicate": False,
        "form_metadata": {
            "response_id": response_id,
            "submission_time": datetime.now().isoformat(),
        },
        "debug_info": {
            "timestamp": datetime.now().isoformat(),
            "source": "main_deployment",
            "trigger_id": trigger_id,
            "pdf_size_bytes": len(pdf_content),
        },
    }

    try:
        logger.info(
            "Triggering Power Automate for %s (trigger_id: %s)",
            recipient_email,
            trigger_id,
        )
        logger.info("Power Automate URL: %s...", power_automate_url[:50])
        logger.info("PDF size: %s bytes", len(pdf_content))

        response = requests.post(
            power_automate_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60,  # Increased timeout for larger payloads
        )

        logger.info("Power Automate response: %s", response.status_code)
        logger.info("Power Automate response body: %s", response.text[:200])

        success = response.status_code < 400

        # Record successful Power Automate trigger to prevent duplicates
        if success:
            record_power_automate_triggered(trigger_id, f"direct_pdf_{response_id}")

        return success

    except requests.exceptions.Timeout:
        logger.error("Power Automate request timed out")
        return False
    except requests.exceptions.RequestException as e:
        logger.exception("Error triggering Power Automate: %s", e)
        return False


def check_power_automate_triggered(trigger_id: str) -> bool:
    """
    Check if Power Automate has already been triggered for this request
    """
    try:
        client = storage.Client()
        bucket = client.bucket(LAST_ID_BUCKET)
        blob = bucket.blob("power_automate_triggered.txt")

        if blob.exists():
            triggered_data = blob.download_as_text()
            triggered_ids = [
                line.split(":")[0]
                for line in triggered_data.splitlines()
                if ":" in line
            ]
            return trigger_id in triggered_ids

        return False

    except Exception as e:
        logger.exception("Error checking Power Automate trigger: %s", e)
        return False


def record_power_automate_triggered(trigger_id: str, pdf_path: str):
    """
    Record that Power Automate has been triggered for this request
    """
    try:
        client = storage.Client()
        bucket = client.bucket(LAST_ID_BUCKET)
        blob = bucket.blob("power_automate_triggered.txt")

        # Get existing content
        existing_content = ""
        if blob.exists():
            existing_content = blob.download_as_text()

        # Add new entry with timestamp
        new_entry = f"{trigger_id}:{pdf_path}:{datetime.now().isoformat()}\n"
        updated_content = existing_content + new_entry

        # Upload updated content
        blob.upload_from_string(updated_content)
        logger.info("Recorded Power Automate trigger: %s", trigger_id)

    except Exception as e:
        logger.exception("Error recording Power Automate trigger: %s", e)


async def run_advisor(
    manual: bool = False, webhook_payload: dict = None, return_pdf_content: bool = False
):
    """
    Main advisor pipeline function with enhanced duplicate prevention and optional PDF content return

    Args:
        manual: Use manual test data
        webhook_payload: Webhook data from Typeform
        return_pdf_content: If True, return PDF content in result for direct transmission
    """
    logger.info("=== Starting Advisor Pipeline ===")
    TMP_DIR = get_tmp_dir()
    FINAL_OUTPUT_DIR = get_final_output_dir()

    # Initialize variables
    recipient_email = None
    organization = None
    response_id = "manual"
    gcs_pdf_path = None
    local_pdf_path = None

    # ----------------------------
    # Step 1: Load Typeform data and handle duplicates
    # ----------------------------
    if manual:
        logger.info("Using manual Typeform response for testing purposes...")
        with open(MANUAL_RESPONSE_FILE) as f:
            responses = json.load(f)

        # For manual mode, use timestamp-based path
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        pdf_file_name = f"final_recommendation_{timestamp}.pdf"
        local_pdf_path = Path(f"xbi_advisor/final_recommendation/{pdf_file_name}")
        gcs_pdf_path = f"gs://{LAST_ID_BUCKET}/manual/{pdf_file_name}"

    elif webhook_payload:
        logger.info("Using provided webhook payload from Typeform webhook...")

        # Extract info from webhook payload
        raw = webhook_payload.get("form_response", {})
        response_id = raw.get("token")

        # Extract recipient info
        recipient_email = extract_email(webhook_payload)
        organization = extract_organization(webhook_payload)

        if not recipient_email:
            logger.error("No email found in webhook payload")
            return {"status": "error", "message": "No email found"}

        if not response_id:
            logger.error("No response ID found in webhook payload")
            return {"status": "error", "message": "No response ID found"}

        logger.info(
            "Processing request for: %s (Response ID: %s)", recipient_email, response_id
        )

        # FINAL duplicate check (should have been caught earlier, but safety check)
        if check_duplicate_response(response_id):
            logger.warning(
                "FINAL DUPLICATE CHECK: Response %s already processed", response_id
            )

            # Try to find existing PDF
            existing_pdf_path = find_existing_pdf_for_response_id(
                response_id, recipient_email, organization
            )

            if existing_pdf_path:
                logger.info("Found existing PDF: %s", existing_pdf_path)
                return {
                    "status": "duplicate_with_pdf",
                    "response_id": response_id,
                    "pdf_path": existing_pdf_path,
                    "recipient_email": recipient_email,
                    "message": "Duplicate response but PDF found",
                }
            else:
                logger.warning(
                    "Duplicate response but no PDF found. This shouldn't happen!"
                )
                return {
                    "status": "duplicate_no_pdf",
                    "response_id": response_id,
                    "recipient_email": recipient_email,
                    "message": "Duplicate response without PDF",
                }

        # Generate unique PDF path
        gcs_pdf_path, local_pdf_path = generate_unique_pdf_path(
            recipient_email, response_id, organization
        )

        logger.info("Generated unique PDF path: %s", gcs_pdf_path)

        # Prepare API-like format
        api_like = {
            "response_id": response_id,
            "submitted_at": raw.get("submitted_at"),
            "landed_at": raw.get("landed_at"),
            "metadata": raw.get("metadata", {}),
            "calculated": raw.get("calculated", {}),
            "answers": raw.get("answers", []),
        }

        # Map field IDs to question text
        client = TypeformClient()
        field_map = client.get_form_structure(raw.get("form_id", ""))
        formatter = TypeformResponseFormatter(field_map)
        formatted_response = formatter.format_response(api_like)
        logger.info(
            "Formatted answers keys: %s",
            list(formatted_response.get("answers", {}).keys()),
        )

        responses = [formatted_response]

    else:
        logger.info("Retrieving latest Typeform data from API...")
        responses = process_typeform_data(TYPEFORM_OUTPUT_DIR)

        # For API mode, use timestamp-based path
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        pdf_file_name = f"final_recommendation_{timestamp}.pdf"
        local_pdf_path = FINAL_OUTPUT_DIR / pdf_file_name
        gcs_pdf_path = f"gs://{LAST_ID_BUCKET}/api/{pdf_file_name}"

    # ----------------------------
    # Step 2: Convert to YAML
    # ----------------------------
    logger.info("Step 2: Converting responses to YAML...")
    process_typeform_responses(responses, TMP_DIR / "user_input", QUESTION_MAPPING_FILE)

    # ----------------------------
    # Step 3: Merge YAMLs
    # ----------------------------
    logger.info("Step 3: Merging YAML data...")
    combined_data = get_flattened_content(ASSETS_DIR)

    # ----------------------------
    # Step 4: LLM scoring
    # ----------------------------
    logger.info("Step 4: Generating LLM scores...")
    template_text_scores = SCORES_TEMPLATE_FILE.read_text(encoding="utf-8")
    llm_scores = await generate_llm_scores(combined_data, template_text_scores)

    # ----------------------------
    # Step 5: Rules engine
    # ----------------------------
    logger.info("Step 5: Loading rules and calculating rule-based recommendations...")
    match_result = None
    try:
        engine = RulesEngine.from_yaml(RULES_FILE)
        match_result = engine.match(combined_data)
        # DIAGNOSTIC: Check rules matching results
        matched_count = sum(len(v) for v in match_result.category_matches.values())
        logger.info(
            "RULES: %s matched | Categories: %s",
            matched_count,
            list(match_result.category_matches.keys()),
        )
    except (FileNotFoundError, ValueError, KeyError, AttributeError) as e:
        logger.warning("Could not load rules engine: %s", e)
        engine = None

    # ----------------------------
    # Step 6: Final advice
    # ----------------------------
    logger.info("Step 6: Generating final advice with combined LLM scores and rules...")
    template_text_recommendation = RECOMMENDATION_TEMPLATE_FILE.read_text(
        encoding="utf-8"
    )
    prompt = create_prompt(
        combined_data, template_text_recommendation, llm_scores, match_result
    )
    # DIAGNOSTIC: Check prompt contains scoring data
    logger.info(
        "PROMPT: %s chars | Has scoring: %s", len(prompt), "Category Matches" in prompt
    )

    final_advice = await response_from_openai(prompt)
    # DIAGNOSTIC: Check LLM response has real scores
    has_numbers = bool(re.search(r"\|\s*\d+\s*\|", final_advice))
    logger.info(
        "RESPONSE: %s chars | Has ...: %s | Has numbers: %s",
        len(final_advice),
        "..." in final_advice,
        has_numbers,
    )
    logger.info("Final advice generated (length: %d chars).", len(final_advice))

    # ----------------------------
    # Step 7: Save Markdown
    # ----------------------------
    logger.info("Step 7: Saving markdown file...")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    markdown_file_name = f"xbi_advisor_{timestamp}.md"
    markdown_file = FINAL_OUTPUT_DIR / markdown_file_name
    markdown_file.parent.mkdir(parents=True, exist_ok=True)

    with open(markdown_file, "w") as f:
        f.write(final_advice)
    logger.info("Recommendation saved to %s", markdown_file)

    # ----------------------------
    # Step 8: Generate PDF with unique path
    # ----------------------------
    logger.info("Step 8: Generating PDF with unique path...")

    # Ensure directory exists
    local_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    pdf_success = generate_pdf(final_advice, local_pdf_path)

    if not pdf_success:
        logger.error("PDF generation failed")
        return {"status": "error", "message": "PDF generation failed"}

    logger.info("PDF saved to %s", local_pdf_path)

    # ----------------------------
    # Step 9: Read PDF content for direct transmission (optional)
    # ----------------------------
    pdf_content = None
    if return_pdf_content or webhook_payload:  # Always read for webhook payloads
        try:
            with open(local_pdf_path, "rb") as f:
                pdf_content = f.read()
            logger.info("PDF content read: %s bytes", len(pdf_content))
        except OSError as e:
            logger.error("Failed to read PDF content: %s", e)
            return {"status": "error", "message": "Failed to read PDF content"}

    # ----------------------------
    # Step 10: Record processing completion BEFORE any external triggers
    # ----------------------------
    if webhook_payload and response_id != "manual":
        logger.info("Step 10: Recording processing completion...")
        record_processed_response(response_id, gcs_pdf_path)

        # Also save using old method for backward compatibility
        try:
            save_last_id_to_gcs(response_id)
        except Exception as e:
            logger.error("Could not save last processed ID: %s", e)

    # ----------------------------
    # Step 11: Send PDF directly to Power Automate (only for webhook requests)
    # ----------------------------
    if recipient_email and webhook_payload and not manual and pdf_content:
        logger.info("Step 11: Sending PDF directly to Power Automate...")
        pa_success = trigger_power_automate_with_pdf(
            pdf_content, recipient_email, response_id, organization
        )

        if pa_success:
            logger.info("Power Automate triggered successfully with PDF")
        else:
            logger.error("Power Automate trigger failed")

    # ----------------------------
    # Final return payload
    # ----------------------------
    result = {
        "status": "success",
        "pdf_path": gcs_pdf_path,
        "local_path": str(local_pdf_path),
        "markdown": str(markdown_file),
        "response_id": response_id,
        "recipient_email": recipient_email,
    }

    # Include PDF content in result if requested
    if return_pdf_content and pdf_content:
        result["pdf_content"] = pdf_content
        result["pdf_size"] = len(pdf_content)

    logger.info("Pipeline completed successfully!")
    logger.info("PDF generated at: %s", gcs_pdf_path)
    return result


def main():
    """
    Command line entry point for testing
    """
    parser = argparse.ArgumentParser(description="Run XBI Advisor analysis")
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Use manual Typeform response instead of API.",
    )
    args = parser.parse_args()

    result = asyncio.run(run_advisor(manual=args.manual))

    if result.get("status") == "success":
        logger.info("Pipeline completed successfully!")
        logger.info("PDF generated at: %s", result.get("pdf_path"))
    else:
        logger.error("Pipeline failed: %s", result.get("message", "Unknown error"))
        return 1

    return 0


if __name__ == "__main__":
    main()

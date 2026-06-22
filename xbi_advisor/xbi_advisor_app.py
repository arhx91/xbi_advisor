"""FastAPI application — webhook entry point for the XBI Advisor service on Cloud Run."""

import logging
import os
import uuid
from datetime import datetime

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import Response
from google.cloud import storage

from .main_deployment import (
    extract_email,
    extract_organization,
    find_existing_pdf_for_response_id,
    run_advisor,
)

logger = logging.getLogger(__name__)
app = FastAPI()

# Global set to track processing requests (in-memory)
PROCESSING_REQUESTS = set()


@app.get("/")
def health_check():
    return {"status": "ok", "service": "XBI Advisor API", "version": "2.0"}


def check_duplicate_response_immediate(response_id: str) -> bool:
    """
    Immediate duplicate check using GCS - synchronous version for webhook handler
    """
    try:
        client = storage.Client()
        bucket = client.bucket("xbi-advisor-bucket")  # Use your bucket name
        blob = bucket.blob("processed_responses.txt")

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


def record_processing_start(response_id: str):
    """
    Record that processing has started (to prevent race conditions)
    """
    try:
        client = storage.Client()
        bucket = client.bucket("xbi-advisor-bucket")
        blob = bucket.blob("processing_started.txt")

        # Get existing content
        existing_content = ""
        if blob.exists():
            existing_content = blob.download_as_text()

        # Add new entry with timestamp
        new_entry = f"{response_id}:{datetime.now().isoformat()}\n"
        updated_content = existing_content + new_entry

        # Upload updated content
        blob.upload_from_string(updated_content)
        logger.info("Recorded processing start: %s", response_id)

    except Exception as e:
        logger.exception("Error recording processing start: %s", e)


def check_processing_started(response_id: str) -> bool:
    """
    Check if processing has already started for this response (last 10 minutes)
    """
    try:
        client = storage.Client()
        bucket = client.bucket("xbi-advisor-bucket")
        blob = bucket.blob("processing_started.txt")

        if blob.exists():
            processing_data = blob.download_as_text()
            for line in processing_data.splitlines():
                if line.startswith(response_id + ":"):
                    # Check if it's recent (within 10 minutes)
                    timestamp_str = line.split(":", 1)[1].strip()
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str)
                        time_diff = datetime.now() - timestamp
                        if time_diff.total_seconds() < 600:  # 10 minutes
                            return True
                    except ValueError:
                        pass

        return False

    except Exception as e:
        logger.exception("Error checking processing started: %s", e)
        return False


@app.post("/webhook")
async def webhook_handler(request: Request, background_tasks: BackgroundTasks):
    """
    Enhanced webhook endpoint with immediate duplicate prevention and simplified Power Automate integration
    """
    request_id = str(uuid.uuid4())[:8]

    try:
        payload = await request.json()
        logger.info("[%s] Received webhook payload", request_id)

        # Extract response ID immediately
        form_response = payload.get("form_response", {})
        response_id = form_response.get("token")

        if not response_id:
            logger.error("[%s] No response ID found in payload", request_id)
            return {
                "status": "error",
                "message": "No response ID found",
                "request_id": request_id,
            }

        logger.info("[%s] Processing response ID: %s", request_id, response_id)

        # IMMEDIATE duplicate checks (before background processing)

        # Check 1: In-memory processing set
        if response_id in PROCESSING_REQUESTS:
            logger.warning(
                "[%s] Response %s is already being processed (in-memory)",
                request_id,
                response_id,
            )
            return {
                "status": "duplicate",
                "message": "Already processing",
                "request_id": request_id,
            }

        # Check 2: Already completed processing
        if check_duplicate_response_immediate(response_id):
            logger.warning(
                "[%s] Response %s already processed (completed)",
                request_id,
                response_id,
            )
            return {
                "status": "duplicate",
                "message": "Already processed",
                "request_id": request_id,
            }

        # Check 3: Processing started recently
        if check_processing_started(response_id):
            logger.warning(
                "[%s] Response %s processing started recently", request_id, response_id
            )
            return {
                "status": "duplicate",
                "message": "Processing started",
                "request_id": request_id,
            }

        # Check Power Automate webhook URL
        power_automate_url = os.getenv("POWER_AUTOMATE_WEBHOOK_URL")
        if not power_automate_url:
            logger.error("[%s] POWER_AUTOMATE_WEBHOOK_URL not configured!", request_id)
            return {
                "status": "error",
                "message": "Power Automate webhook URL not configured",
            }

        # Mark as processing (both in-memory and GCS)
        PROCESSING_REQUESTS.add(response_id)
        record_processing_start(response_id)

        # Extract email immediately for validation
        recipient_email = extract_email(payload)
        if not recipient_email:
            logger.error("[%s] No recipient email found", request_id)
            PROCESSING_REQUESTS.discard(response_id)  # Remove from processing set
            return {
                "status": "error",
                "message": "No email found",
                "request_id": request_id,
            }

        # Schedule background processing
        background_tasks.add_task(
            process_webhook_payload_safe, payload, request_id, response_id
        )

        logger.info(
            "[%s] Scheduled background processing for %s", request_id, response_id
        )
        return {
            "status": "accepted",
            "request_id": request_id,
            "response_id": response_id,
        }

    except Exception as e:
        logger.exception("[%s] Webhook parse failed", request_id)
        return {"status": "error", "message": str(e), "request_id": request_id}


@app.get("/pdf/{response_id}")
async def get_pdf_direct(response_id: str):
    """
    Direct PDF endpoint - generates and returns PDF immediately
    This is the NEW simplified approach for Power Automate
    """
    try:
        logger.info("Direct PDF request for response_id: %s", response_id)

        # This would need to be implemented to get the original webhook payload
        # For now, return error if trying to regenerate from just response_id
        logger.error("Direct PDF regeneration not implemented - need original payload")
        raise HTTPException(
            status_code=404, detail="PDF regeneration from response_id not supported"
        )

    except Exception as e:
        logger.exception("Error in direct PDF endpoint: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-pdf-direct")
async def generate_pdf_direct_endpoint(request: Request):
    """
    Direct PDF generation endpoint - receives payload and returns PDF immediately
    This is the RECOMMENDED approach for Power Automate integration
    """
    try:
        payload = await request.json()
        logger.info("Direct PDF generation request received")

        # Extract response ID
        form_response = payload.get("form_response", {})
        response_id = form_response.get("token", "direct_request")

        # Extract email
        recipient_email = extract_email(payload)
        if not recipient_email:
            raise HTTPException(status_code=400, detail="No email found in payload")

        logger.info(
            "Generating PDF directly for %s (Response: %s)",
            recipient_email,
            response_id,
        )

        # Check for duplicates
        if check_duplicate_response_immediate(response_id):
            logger.info(
                "Duplicate request for %s - looking for existing PDF", response_id
            )
            # Try to find and return existing PDF
            existing_pdf = find_existing_pdf_for_response_id(
                response_id, recipient_email
            )
            if existing_pdf:
                # For direct endpoint, we'd need to read from GCS and return
                # This is complex, so for now return reference
                return {"status": "duplicate", "pdf_path": existing_pdf}

        # Run the advisor pipeline with PDF content return
        result = await run_advisor(
            manual=False, webhook_payload=payload, return_pdf_content=True
        )

        if result.get("status") != "success":
            raise HTTPException(
                status_code=500, detail=result.get("message", "Pipeline failed")
            )

        pdf_content = result.get("pdf_content")
        if not pdf_content:
            raise HTTPException(status_code=500, detail="No PDF content generated")

        # Return PDF directly as response
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=XBI_Recommendation_{response_id}.pdf"
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in direct PDF generation")
        raise HTTPException(status_code=500, detail=str(e))


async def process_webhook_payload_safe(
    payload: dict, request_id: str, response_id: str
):
    """
    Safe wrapper for processing that ensures cleanup
    """
    try:
        await process_webhook_payload(payload, request_id)
    except Exception as e:
        logger.exception("[%s] Error in background processing: %s", request_id, e)
    finally:
        # Always remove from processing set when done
        PROCESSING_REQUESTS.discard(response_id)
        logger.info("[%s] Removed %s from processing set", request_id, response_id)


async def process_webhook_payload(payload: dict, request_id: str = "unknown"):
    """
    Background processing - generates PDF and sends directly to Power Automate
    The PDF content is now sent directly instead of requiring a separate download
    """
    try:
        logger.info("[%s] Starting background processing...", request_id)

        # Extract basic info
        recipient_email = extract_email(payload)
        organization = extract_organization(payload)
        response_id = payload.get("form_response", {}).get("token")

        logger.info(
            "[%s] Processing: email=%s, org=%s, id=%s",
            request_id,
            recipient_email,
            organization,
            response_id,
        )

        if not recipient_email:
            logger.error("[%s] No recipient email found - cannot proceed", request_id)
            return

        # Double-check for duplicates before heavy processing
        if check_duplicate_response_immediate(response_id):
            logger.warning(
                "[%s] Duplicate detected during processing - aborting", request_id
            )
            return

        # Run advisor with PDF content return
        logger.info("[%s] Calling run_advisor...", request_id)
        result = await run_advisor(
            manual=False, webhook_payload=payload, return_pdf_content=True
        )
        logger.info("[%s] Pipeline result: %s", request_id, result.get("status"))

        # The run_advisor function now handles the Power Automate trigger internally
        # with the PDF content, so no additional trigger is needed here

        if result.get("status") == "success":
            logger.info(
                "[%s] Processing completed successfully - PDF sent to Power Automate",
                request_id,
            )
        elif result.get("status") == "duplicate_with_pdf":
            logger.info(
                "[%s] Duplicate with existing PDF - no action needed", request_id
            )
        else:
            logger.warning(
                "[%s] Processing failed: %s",
                request_id,
                result.get("message", "Unknown error"),
            )

    except Exception as e:
        logger.exception("[%s] Error in process_webhook_payload: %s", request_id, e)


@app.get("/test-connection")
async def test_connection():
    return {"status": "success", "service": "XBI Advisory API", "version": "2.0"}


@app.get("/debug/processing-status")
async def debug_processing_status():
    """
    Debug endpoint to check current processing status
    """
    return {
        "in_memory_processing": list(PROCESSING_REQUESTS),
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/test-pdf")
async def test_pdf_generation(request: Request):
    """
    Test endpoint for PDF generation without webhook
    """
    try:
        # Use manual test data
        result = await run_advisor(manual=True, return_pdf_content=True)

        if result.get("status") != "success":
            raise HTTPException(status_code=500, detail="Test PDF generation failed")

        pdf_content = result.get("pdf_content")
        if not pdf_content:
            raise HTTPException(status_code=500, detail="No PDF content generated")

        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=test_recommendation.pdf"
            },
        )

    except Exception as e:
        logger.exception("Error in test PDF generation")
        raise HTTPException(status_code=500, detail=str(e))

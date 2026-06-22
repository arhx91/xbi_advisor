import logging

# Clear any existing handlers
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Configure the root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

import argparse
import asyncio
import json
from pathlib import Path

from xbi_advisor.export_typeform_responses import process_typeform_responses
from xbi_advisor.generate_pdf import generate_pdf
from xbi_advisor.llm import (
    add_images_to_advice,
    create_prompt,
    generate_llm_scores,
    response_from_openai,
)
from xbi_advisor.parser import get_flattened_content
from xbi_advisor.rules_engine import RulesEngine
from xbi_advisor.typeform_output import process_typeform_data

ASSETS_DIR = Path("xbi_advisor/assets")
USER_INPUT_DIR = ASSETS_DIR / "user_input"
TEMPLATES_DIR = ASSETS_DIR / "templates"
TYPEFORM_OUTPUT_DIR = Path("xbi_advisor/typeform_output")
TMP_DIR = Path("xbi-advisor/tmp")

RULES_FILE = ASSETS_DIR / "rules/rules.yaml"
MANUAL_RESPONSE_FILE = Path("examples/manual_responses.json")
QUESTION_MAPPING_FILE = TEMPLATES_DIR / "question_mapping.json"
MARKDOWN_OUTPUT_FILE = Path("tmp/xbi_advisor.md")
SCORES_TEMPLATE_FILE = TEMPLATES_DIR / "scores_template.md"
RECOMMENDATION_TEMPLATE_FILE = TEMPLATES_DIR / "recommendation_template.md"


async def _run():
    parser = argparse.ArgumentParser(
        description="Using manual Typeform response for testing purposes"
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Use manual Typeform response for testing purposes instead of fetching new data",
    )
    args = parser.parse_args()

    # Only run optional scripts if specified
    if args.manual:
        logger.info("Using manual Typeform response for testing purposes...")
        with open(MANUAL_RESPONSE_FILE) as f:
            responses = json.load(f)
    else:
        logger.info("Retrieving latest Typeform data...")
        responses = process_typeform_data(TYPEFORM_OUTPUT_DIR)

    process_typeform_responses(responses, USER_INPUT_DIR, QUESTION_MAPPING_FILE)

    combined_data = get_flattened_content(ASSETS_DIR)
    template_text_scores = SCORES_TEMPLATE_FILE.read_text(encoding="utf-8")

    logger.info("Step 1: Generating LLM scores.")
    llm_scores = await generate_llm_scores(
        combined_data,
        template_text_scores,
    )

    template_text_recommendation = RECOMMENDATION_TEMPLATE_FILE.read_text(
        encoding="utf-8"
    )

    logger.info("Step 2: Loading rules and calculating rule-based recommendations.")

    # Check if rules file exists
    if not RULES_FILE.exists():
        logger.error("Rules file not found: %s", RULES_FILE)
        raise FileNotFoundError(f"Rules file not found: {RULES_FILE}")

    logger.info("Loading rules from %s", RULES_FILE)

    engine = RulesEngine.from_yaml(RULES_FILE)
    logger.info("Successfully loaded %s rules", len(engine.rules))

    logger.info("Matching rules against user input data...")
    match_result = engine.match(combined_data)
    logger.info("Rule matching completed successfully")

    logger.info("Step 3: Generating final advice with combined LLM scores and rules.")
    prompt = create_prompt(
        combined_data, template_text_recommendation, llm_scores, match_result
    )

    final_advice = await response_from_openai(prompt)
    final_advice_with_images = add_images_to_advice(
        final_advice, "BI_comparisons.png", 600, "3. Exploring BI Options"
    )

    logger.info(
        "Final advice generated (length: %d chars).", len(final_advice_with_images)
    )

    with open(MARKDOWN_OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(final_advice_with_images)
    logger.info("Recommendation saved to %s", MARKDOWN_OUTPUT_FILE)

    pdf_file = Path("xbi_advisor/final_recommendation/final_recommendation.pdf")

    generate_pdf(final_advice_with_images, pdf_file)


def main():
    asyncio.run(_run())


if __name__ == "__main__":
    main()

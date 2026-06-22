"""
This module processes Typeform survey responses and converts them into structured YAML files for use in the advisory workflow.

What it does:
    - Loads Typeform response data and a question-to-category mapping.
    - Extracts the latest response and maps answers to structured categories and fields.
    - Writes the processed profile as a YAML file for downstream use.

Why:
    - Automates the transformation of raw survey data into a format suitable for rules engine and LLM processing.

How:
    - Uses JSON for input/output and YAML for structured output.
    - Handles errors and missing data gracefully.

Integration:
    - Called by the main pipeline (__main__.py) to prepare user input data.
    - Output YAML is consumed by parser.py and other modules.
"""

import json
import logging
import os
from datetime import datetime

from ruamel.yaml import YAML

logger = logging.getLogger(__name__)


def load_question_map(question_map_path: str) -> dict:
    # Loads and returns the question-to-category mapping from JSON file
    try:
        with open(question_map_path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Question map file not found: {question_map_path}")


def get_timestamp(response: dict) -> datetime:
    # Sort responses by 'submitted_at' in descending order (latest first)
    # Parse strings to datetime objects for proper chronological sorting
    timestamp = response.get("submitted_at")
    if not timestamp:
        logger.info("no timestamp")
        return datetime.min  # Earliest possible date if missing
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        logger.info("Warning: Could not parse timestamp: %s", timestamp)
        return datetime.min


def get_latest_response(responses: list[dict]) -> dict:
    # Sorts responses to get the latest one
    if not responses:
        logger.info("No response found")
        return {}

    responses.sort(key=get_timestamp, reverse=True)
    logger.info(
        "Latest response: %s at %s",
        responses[0]["response_id"],
        responses[0]["submitted_at"],
    )
    return responses[0]


def create_empty_profile(response_id: str, submittted_at: str) -> dict:
    # Creates an empty profile structure with basic metadata
    return {
        "respondent_id": response_id,
        "submitted_at": submittted_at,
        "user_info": {},
        "ecosystem": {},
        "security": {},
        "data_governance": {},
        "maturity_level": {},
        "capabilities": {},
        "pricing": {},
        "pain_points": {},
    }


def map_answers_to_profile(answers: dict, question_map: dict, profile: dict) -> dict:
    # Maps answers to their corresponding categories in the profile
    answer_dict = answers.get("answers", answers)  # Handle both nested and flat formats
    for question, answer in answer_dict.items():
        mapped = question_map.get(question.strip())
        if mapped:
            category, field = mapped
            profile[category][field] = answer
    return profile


def save_profile_to_yaml(profile: dict, output_dir: str) -> None:
    # Saves the profile to a YAML file
    os.makedirs(output_dir, exist_ok=True)  # Ensure the directory exists
    filename = "user_input.yaml"
    output_path = os.path.join(output_dir, filename)
    yaml = YAML()
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(profile, f)


def process_typeform_responses(
    responses: list[dict], output_dir: str, question_map_path: str
) -> None:
    """
    Processes Typeform responses, extracts relevant fields
    based on a question-to-category mapping, and writes the latest response
    as a YAML profile file.

    Args:
        responses (list[dict]): Typeform responses in memory.
        output_dir (str): Directory where the YAML profile file will be saved.
        question_map_path (str): Path to the JSON file that maps question titles
                                 to (category, field) tuples.
    """

    question_map = load_question_map(question_map_path)
    latest_response = get_latest_response(responses)
    profile = create_empty_profile(
        latest_response["response_id"], latest_response["submitted_at"]
    )
    profile = map_answers_to_profile(latest_response, question_map, profile)
    save_profile_to_yaml(profile, output_dir)

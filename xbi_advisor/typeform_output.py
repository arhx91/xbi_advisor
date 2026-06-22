"""
This module handles fetching, formatting, and saving Typeform survey data for use in the BI advisory workflow.

What it does:
    - Provides classes and functions to interact with the Typeform API.
    - Downloads form metadata and responses, formats them, and saves them as JSON files.

Why:
    - To automate the retrieval and structuring of survey data for downstream processing.

How:
    - Uses requests to call the Typeform API and dotenv for environment variable management.
    - Formats responses into human-readable dictionaries and saves them to disk.

Integration:
    - Used by the main pipeline and export_typeform_responses.py to obtain and process survey data.
    - Outputs are consumed by parser.py and other modules for further analysis.
"""

import json
import logging
import os

import requests

logger = logging.getLogger(__name__)


class TypeformAPI:
    """Handles raw API interactions with Typeform."""

    BASE_URL = "https://api.typeform.com"

    def __init__(self, headers: dict) -> None:
        self.headers = headers

    def _make_request(self, endpoint: str) -> dict:
        # Make a GET request to the Typeform API
        url = f"{self.BASE_URL}/{endpoint}"
        resp = requests.get(url, headers=self.headers)
        return resp.json() if resp.ok else {}

    def get_forms(self) -> list[dict]:
        # Fetch list of forms from API
        return self._make_request("forms").get("items", [])

    def get_form_fields(self, form_id: str) -> list[dict]:
        # Fetch form structure from API
        return self._make_request(f"forms/{form_id}").get("fields", [])

    def get_responses(self, form_id: str) -> list[dict]:
        # Fetch form responses from API
        return self._make_request(f"forms/{form_id}/responses").get("items", [])


class TokenManager:
    """Handles API token management."""

    def get_token(token: str | None = None) -> str:
        # Get and validate API token
        token = token or os.getenv("TYPEFORM_TOKEN")
        if not token:
            raise ValueError("TYPEFORM_TOKEN not set.")
        return token

    def mask_token(token: str) -> str:
        # Create a masked version of the token for logging
        return f"{token[:6]}...{token[-4:]}"


class TypeformClient:
    """Client for interacting with the Typeform API."""

    def __init__(self, token: str | None = None) -> None:
        self.token = TokenManager.get_token(token)
        masked_token = TokenManager.mask_token(self.token)
        logger.debug("Loaded token: %s", masked_token)

        self.api = TypeformAPI({"Authorization": f"Bearer {self.token}"})

    def list_forms(self) -> list[dict]:
        # Get list of available forms
        logger.info("Fetching list of forms...")
        return self.api.get_forms()

    def get_form_structure(self, form_id: str) -> dict[str, str]:
        # Get form field structure
        fields = self.api.get_form_fields(form_id)
        return {f["id"]: f.get("title", "<no title>") for f in fields}

    def get_form_responses(self, form_id: str) -> list[dict]:
        # Get form responses
        return self.api.get_responses(form_id)


class ResponseFormatter:
    def format_metadata(response: dict) -> dict:
        # Extract metadata from response
        return {
            "response_id": response.get("response_id"),
            "submitted_at": response.get("submitted_at"),
            "landed_at": response.get("landed_at"),
        }

    def extract_answer_value(answer: dict) -> any:
        # Extract actual value fron an answer object
        answer_type = answer.get("type")
        raw = answer.get(answer_type)
        return raw.get("label") if isinstance(raw, dict) and "label" in raw else raw


class TypeformResponseFormatter:
    """Formats Typeform responses into human-readable dictionaries."""

    def __init__(self, field_map: dict[str, str]) -> None:
        """
        Initialize the formatter with a field ID to question title mapping.

        Args:
            field_map (Dict[str, str]): Mapping from field IDs to question titles.
        """
        self.field_map = field_map

    def format_empty_response(self, response: dict) -> dict:
        # Format response with no answers
        result = ResponseFormatter.format_metadata(response)
        result["note"] = "No answers submitted"
        return result

    def format_answers(self, answers: list) -> dict:
        # Format answer list into readable dictionary
        readable_answers = {}

        for answer in answers:
            field_id = answer.get("field", {}).get("id")
            question = self.field_map.get(field_id, f"<Unknown field {field_id}>")
            value = ResponseFormatter.extract_answer_value(answer)
            readable_answers[question] = value

        return readable_answers

    def format_response(self, response: dict) -> dict:
        """
        Format a single Typeform response.

        Args:
            response (Dict): The raw response dictionary from Typeform.

        Returns:
            Dict: A formatted dictionary with readable answers and metadata.
        """
        answers = response.get("answers")
        if not answers:
            return self.format_empty_response(response)

        result = ResponseFormatter.format_metadata(response)
        result.update(
            {
                "answers": self.format_answers(answers),
                "metadata": response.get("metadata", {}),
                "score": response.get("calculated", {}).get("score"),
            }
        )
        return result


class FileHandler:
    """Handles file operations."""

    def save_to_json(data: list[dict], filename: str, output_dir: str) -> None:
        # Save data to JSON file
        path = os.path.join(output_dir, filename)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("Saved to %s", path)
        except Exception as e:
            logger.exception("Could not write file: %s", e)


def process_form(client: TypeformClient, form: dict, output_dir) -> list:
    # Process a single form and its responses
    form_id = form["id"]
    title = form["title"]

    # Save form metadata
    FileHandler.save_to_json([form], f"{form_id}_metadata.json", output_dir)

    # Get and process responses (list[dict])
    responses = client.get_form_responses(form_id)
    if not responses:
        logger.info("No responses found for '%s'", title)
        return []

    # Format responses
    field_map = client.get_form_structure(form_id)
    formatter = TypeformResponseFormatter(field_map)
    return [formatter.format_response(response) for response in responses]


def process_typeform_data(typeform_output_dir: str) -> list[dict]:
    """
    Main function to process Typeform data - can be called from other modules.

    Args:
        print_results (bool): Whether to print results to console
    """
    client = TypeformClient()
    forms = client.list_forms()
    result = {}

    for form in forms:
        form_id = form["id"]
        title = form["title"]

        # Save metadata
        FileHandler.save_to_json(
            [form], f"{form_id}_metadata.json", typeform_output_dir
        )

        # Get and format responses
        responses = client.get_form_responses(form_id)
        if not responses:
            logger.info("No responses found for '%s'", title)
            continue

        field_map = client.get_form_structure(form_id)
        formatter = TypeformResponseFormatter(field_map)
        formatted = []

        for i, response in enumerate(responses, 1):
            formatted_response = formatter.format_response(response)
            formatted.append(formatted_response)

    result[form_id] = formatted

    return formatted

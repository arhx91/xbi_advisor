"""Azure OpenAI integration and prompt-building utilities for the production advisory pipeline."""

import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from jinja2 import Template
from openai import AsyncAzureOpenAI
from ruamel.yaml import YAML

from xbi_advisor.models.match_result import MatchResult
from xbi_advisor.models.types import RuleMatchDict

logger = logging.getLogger(__name__)

# Load .env if not github
if not os.getenv("GITHUB_ACTIONS"):
    load_dotenv()

yaml = YAML(typ="full")


def get_llm_client() -> AsyncAzureOpenAI:
    """
    Initializes and returns an async Azure OpenAI client.
    Reads the following environment variables:
        - AZURE_OPENAI_API_VERSION: API version to use.
        - AZURE_OPENAI_ENDPOINT: Azure OpenAI endpoint URL.
        - AZURE_OPENAI_API_KEY: API key for authentication.
    Returns:
        AsyncAzureOpenAI: An authenticated async Azure OpenAI client instance.
    """
    client = AsyncAzureOpenAI(
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
        azure_endpoint=os.getenv(
            "AZURE_OPENAI_ENDPOINT", "https://xbi-openai-france.openai.azure.com/"
        ),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    )
    return client


def render_prompt_individual_answers(user_input: dict, template_text: str) -> str:
    """
    Renders the prompt for the OpenAI API to assign individual scores on the open ended questions
    """
    company_name = user_input.get("user_input", {}).get("company_name", "there")
    rendered_template = Template(template_text).render(company_name=company_name)
    prompt = rendered_template + "\n\nHere are the categories and answers:"
    for name, config in user_input.items():
        prompt += f"\n### {name} Configuration:\n{json.dumps(config)}\n"
    return prompt


def render_prompt(user_input: dict, template_text: str) -> str:
    """
    Renders a prompt for the OpenAI API using a Jinja2 template and user input data.
    Args:
        user_input (dict): Dictionary containing user-specific configuration and company name.
        template_text (str): Jinja2 template as a string to be rendered.
    Returns:
        str: Fully rendered prompt string to be sent to the OpenAI API.
    """
    company_name = user_input.get("user_input", {}).get("company_name", "there")
    rendered_template = Template(template_text).render(company_name=company_name)
    prompt = (
        rendered_template
        + "\n\nHere are the company's data and current BI setup details:\n"
    )
    for name, config in user_input.items():
        prompt += f"\n### {name} Configuration:\n{json.dumps(config)}\n"
    return prompt


def render_prompt_with_context(template_str: str, context: dict) -> str:
    """
    Render any Jinja2 prompt with a given context dictionary.

    Args:
        template_str (str): Jinja2 template string.
        context (dict): Context dictionary to be used for rendering the template.

    Returns:
        str: Rendered string from the Jinja2 template using the provided context.
    """
    return Template(template_str).render(**context)


async def response_from_openai(prompt: str) -> str:
    """
    Sends a chat completion request to the Azure OpenAI API and returns the response.
    Args:
        prompt (str): The prompt string to send to the OpenAI model.
    Returns:
        str: The content of the model's response.
    """
    client = get_llm_client()
    response = await client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "o4-mini"),
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert BI tool advisor. "
                    "IMPORTANT: Preserve any HTML <img> tags exactly as they appear in the template. "
                    "Do not modify or remove image tags."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=1,
    )
    return response.choices[0].message.content


def add_images_to_advice(
    final_advice: str,
    image_path: str,
    width: int = 500,
    section_header: str | None = None,
) -> str:
    """Add images at specific locations in the final advice"""
    logger.info("Image path:")
    logger.info(
        '<img src="xbi_advisor/assets/images/%s" style="width: %spx;">\n\n',
        image_path,
        width,
    )
    logo_path = os.path.abspath(f"xbi_advisor/assets/images/{image_path}")

    if (
        section_header is None or f"## {section_header}" not in final_advice
    ):  # Add logo at the beginning
        logo = f'<img src="file://{logo_path}" style="width: {width}px;">\n\n'

        final_advice = logo + final_advice
        logger.info("Added image at the beginning")

    # Add chart after "## Tool Comparison" section
    if f"## {section_header}" in final_advice:
        final_advice = final_advice.replace(
            f"## {section_header}",
            f'## {section_header}\n\n<img src="file://{logo_path}" style="width: {width}px;">\n',
        )
        logger.info("Added image after section header %s", section_header)

    return final_advice


async def generate_llm_scores(user_input: dict, score_template: str) -> str:
    """
    Generate LLM scores using the original individual answers method.

    Args:
        user_input (dict): User input data structured by configuration categories.
        score_template (str): Template text used to create the prompt for scoring.

    Returns:
        str: LLM generated scoring response based on individual answers.
    """
    prompt = render_prompt_individual_answers(user_input, score_template)
    response = await response_from_openai(prompt)
    return response


async def generate_llm_advice(
    user_input: dict, advice_template: str, scores: str
) -> str:
    """
    Render and submit advice prompt using LLM-generated scores.

    Args:
        user_input (dict): User input data structured by configuration categories.
        advice_template (str): Template text for generating the advice prompt.
        scores (str): Previously generated LLM scores to include in the context.

    Returns:
        str: LLM generated advisory response.
    """
    context = {**user_input, "scores": scores}
    prompt = render_prompt_with_context(advice_template, context)
    return await response_from_openai(prompt)


def create_context(
    respondent_name: str,
    organization_name: str,
    user_input: dict[str, Any],
    llm_scores: str | None,
) -> dict[str, Any]:
    return {
        "respondent_name": respondent_name,
        "organization_name": organization_name,
        "user_input": user_input,
        "llm_scores": llm_scores,
    }


def get_start_prompt(rendered_template: str) -> str:
    # Add the configuration data as before
    return (
        rendered_template
        + "\n\nHere are the company's data and current BI setup details:\n"
    )


def add_configuration_data(
    prompt: str,
    user_input: dict[str, Any],
) -> str:
    # Add the configuration data as before
    for name, config in user_input.items():
        prompt += f"\n### {name} Configuration:\n{json.dumps(config)}\n"
    return prompt


def add_llm_scores(prompt: str, llm_scores: str | None) -> str:
    # Add LLM scores section to prompt
    if llm_scores:
        prompt += "\n### LLM Assessment Scores:\n"
        prompt += llm_scores
    else:
        logger.info("No llm scores available.")
    return prompt


def add_category_matches(
    prompt: str, category_matches: dict[str, list[RuleMatchDict]] | None
) -> str:
    # Add category matches
    if category_matches:
        prompt += "\n### Category Matches Breakdown:\n"
        for category, matches in category_matches.items():
            prompt += f"\nCategory: {category}\n"
            for match in matches:
                prompt += f"  - Rule: {match['id']}\n"
                prompt += f"    Recommendation: {match['recommendation']}\n"
                prompt += f"    Description   : {match['description']}\n"
                prompt += f"    Scores        : {match['scores']}\n"
    else:
        logger.info("No category matches available.")
    return prompt


def create_prompt(
    user_input: dict[str, Any],
    final_template: str,
    llm_scores: str,
    match_result: MatchResult | None = None,
) -> str:
    """
    Generate final advice using both LLM scores and rules engine output.
    Combines original LLM scoring with rules-based recommendations.

    Args:
        user_input (dict): User input data structured by configuration categories.
        final_template (str): Jinja2 template string for the final advice prompt.
        llm_scores (str): LLM generated scores from previous processing.
        match_result (MatchResult | None): Result from RulesEngine.match(), or None if rules engine failed.

    Returns:
        str: Final advice response generated by the LLM incorporating both LLM and rules engine inputs.
    """
    # Get respondent and company name for template rendering
    user_info = user_input.get("user_info", {})
    respondent_name = user_info.get("name", "there")
    organization_name = user_info.get("organization_name", "your organization")

    logger.info(
        "Generating final advice for %s from %s...", respondent_name, organization_name
    )

    context = create_context(respondent_name, organization_name, user_input, llm_scores)

    # Render the template with the full context
    rendered_template = Template(final_template).render(**context)
    prompt = get_start_prompt(rendered_template)
    prompt = add_configuration_data(prompt, user_input)
    prompt = add_llm_scores(prompt, llm_scores)
    if match_result:
        prompt = add_category_matches(prompt, match_result.category_matches)

    return prompt

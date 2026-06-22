"""
Loads and merges YAML configuration files from the assets directory and the runtime temp directory
into a single flat dict consumed by the rules engine and LLM modules.
"""

import logging
from collections.abc import MutableMapping, MutableSequence
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from ruamel.yaml import YAML

from xbi_advisor.models.bi_tools import BiProperties
from xbi_advisor.modules.config import get_tmp_dir

load_dotenv()  # Only affects local dev

logger = logging.getLogger(__name__)
yaml = YAML(typ="safe")


def validate_tool_schema(filename: Path, data: dict) -> None:
    """
    Validates loaded YAML data against the BiProperties Pydantic model.
    Logs warnings for failures or legacy schemas.
    """
    if not data or "bi_tools" not in data:
        return

    for tool in data["bi_tools"]:
        try:
            # Validate against strict schema
            BiProperties(**tool)

            # Custom checks for legacy/incomplete data
            if "pricing" not in tool:
                logger.warning(
                    "Legacy Schema in %s: Missing 'pricing' block (found '%s').",
                    filename.name,
                    "price" if "price" in tool else "None",
                )
            if "tech_stack" not in tool:
                logger.warning(
                    "Legacy Schema in %s: Missing 'tech_stack'.", filename.name
                )

        except Exception as e:
            logger.warning("Schema Validation Failed for %s: %s", filename.name, e)


def yamls_content(assets_dir: Path) -> dict[str, dict]:
    """
    Loads YAML files from:
      1. The static assets directory
      2. The runtime TMP_DIR (for dynamic files)

    Returns:
        dict[str, dict]: Mapping of file paths to parsed YAML dicts (or {} if failed)
    """
    tmp_dir = get_tmp_dir()  ## Note: should work. Check for local development.

    # Directories to search
    search_dirs = [assets_dir, tmp_dir]

    data = {}
    for directory in search_dirs:
        if not directory.exists():
            continue
        for yaml_file in directory.rglob("*.yaml"):
            #  Copy of assets/user_input is an example only
            # Should not be part of (deep) merge, would leak previous respondent's answers into new report when current user has not answered every question (and thus doesn't have filled out user input everywhere)
            if (
                directory == assets_dir
                and "user_input" in yaml_file.relative_to(directory).parts
            ):
                continue
            try:
                with open(yaml_file) as f:
                    parsed = yaml.load(f)
                    if parsed:
                        validate_tool_schema(yaml_file, parsed)
                    data[str(yaml_file)] = parsed if parsed else {}
            except Exception as e:
                logger.warning("Failed to load %s: %s", yaml_file, e)
                data[str(yaml_file)] = {}

    return data


def deep_merge(base: dict, update: dict) -> dict:
    """
    Recursively merges two dictionaries.
    - Lists (MutableSequences) are merged with deduplication:
        - Hashable items (e.g. strings) are added only if unique.
        - Unhashable items (e.g. dicts) are appended (extended).
    - Dicts (MutableMappings) are recursively merged.
    - Other types are overwritten by the value in 'update'.
    """
    for key, value in update.items():
        if key in base:
            if isinstance(base[key], MutableMapping) and isinstance(
                value, MutableMapping
            ):
                deep_merge(base[key], value)
            elif isinstance(base[key], MutableSequence) and isinstance(
                value, MutableSequence
            ):
                try:
                    existing = set(base[key])
                    for item in value:
                        if item not in existing:
                            base[key].append(item)
                            existing.add(item)
                except TypeError:
                    base[key].extend(value)
            else:
                base[key] = value
        else:
            base[key] = value
    return base


def flatten_dictionaries(raw_data: dict[str, Any]) -> dict[str, Any]:
    """
    Flattens a nested dictionary of YAML contents into a single dict.
    Uses deep merging to combine nested dictionaries and extend lists.
    """
    combined_data = {}
    for content in raw_data.values():
        if isinstance(content, MutableMapping):
            deep_merge(combined_data, content)
    return combined_data


def get_flattened_content(assets_dir: Path) -> dict[str, Any]:
    """
    Loads YAML from assets + TMP_DIR, flattens into a single dict.
    """
    raw_data = yamls_content(assets_dir)
    return flatten_dictionaries(raw_data)

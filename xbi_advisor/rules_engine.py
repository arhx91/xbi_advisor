"""Load rules from YAML, match them against user input, and return scored findings."""

import logging
import re
from typing import Any, Self

import yaml
from pydantic import BaseModel
from sentence_transformers import (  # type: ignore[import-untyped,unresolved-import]
    SentenceTransformer,
    util,
)

from xbi_advisor.models.match_result import MatchResult
from xbi_advisor.models.types import RuleMatchDict

MODEL_NAME = "all-MiniLM-L6-v2"

logger = logging.getLogger(__name__)


class Rule(BaseModel):
    """
    A single advisory rule loaded from rules.yaml.

    path: dot-separated field path into the user input dict (e.g. "data_governance.data_ownership").
    match: the expected value — exact string, or a phrase for semantic comparison.
    semantic_similarity: if true, cosine similarity via sentence-transformer replaces exact match.
    category: groups the rule in AdvisoryResult.category_matches; falls back to the path prefix.
    """

    id: str
    path: str
    match: (
        Any  # YAML values are dynamically typed; str | int | bool | list are all valid
    )
    scores: dict[str, int]
    recommendation: str
    description: str = ""
    semantic_similarity: bool = False
    category: str = ""


class RuleMatch:
    """Snapshot of a matched rule, ready to serialise into AdvisoryResult."""

    def __init__(self, rule: Rule) -> None:
        self.id = rule.id
        self.recommendation = rule.recommendation
        self.description = rule.description
        self.scores = rule.scores

    def to_dict(self) -> RuleMatchDict:
        """Return the match as a plain dict."""
        return {
            "id": self.id,
            "recommendation": self.recommendation,
            "description": self.description,
            "scores": self.scores,
        }


class RulesEngine:
    """
    Loads rules from YAML and matches them against user input.

    Each rule is checked with either exact string comparison or cosine similarity
    (when semantic_similarity: true). Matched rules are returned as a MatchResult —
    the engine holds no per-call state.
    """

    _model_cache: dict[str, SentenceTransformer] = {}

    @classmethod
    def _get_model(cls, model_name: str) -> SentenceTransformer:
        if model_name not in cls._model_cache:
            logger.info("Loading sentence-transformer model: %s", model_name)
            cls._model_cache[model_name] = SentenceTransformer(model_name)
        return cls._model_cache[model_name]

    def __init__(self, rules: list[Rule], model_name: str = MODEL_NAME) -> None:
        self.rules = rules
        self.model = self._get_model(model_name)
        self.similarity_threshold = 0.7

    @classmethod
    def from_yaml(cls, yaml_path: str, model_name: str = MODEL_NAME) -> Self:
        """
        Create a RulesEngine by loading rules from a YAML file.

        Args:
            yaml_path (str): Path to the YAML file containing rule definitions.
            model_name (str): Name of the sentence transformer model to use.

        Returns:
            RulesEngine: A new RulesEngine instance with rules loaded from YAML.
        """
        with open(yaml_path) as f:
            rules_data = yaml.safe_load(f)
        rules = [Rule(**rule) for rule in rules_data]
        return cls(rules, model_name)

    def set_similarity_threshold(self, value: float) -> None:
        """Set the similarity threshold for semantic matching."""
        if not 0 <= value <= 1:
            raise ValueError("Similarity threshold must be between 0 and 1")
        self.similarity_threshold = value

    def match(self, user_input: BaseModel | dict | None = None) -> MatchResult:
        """
        Check all rules against user input and return matched results.

        Args:
            user_input: Input data to match rules against. Dict or Pydantic model.

        Returns:
            MatchResult containing matched rules and category groupings.
        """
        if user_input is None:
            return MatchResult(matched_rules=[], category_matches={})

        matched_rules: list[RuleMatchDict] = []
        category_matches: dict[str, list[RuleMatchDict]] = {}
        tool_scores: dict[str, int] = {}

        for rule in self.rules:
            logger.info("Checking rule %s with path '%s'", rule.id, rule.path)
            if self.check_match(rule, user_input):
                match_obj = RuleMatch(rule)
                match_dict = match_obj.to_dict()
                matched_rules.append(match_dict)

                for tool, score in rule.scores.items():
                    tool_scores[tool] = tool_scores.get(tool, 0) + score

                category = rule.category or rule.path.split(".")[0]
                if category not in category_matches:
                    category_matches[category] = []
                category_matches[category].append(match_dict)

        logger.info(
            "Found %d matching rules in %d categories",
            len(matched_rules),
            len(category_matches),
        )
        logger.info("Tool scores from rules: %s", tool_scores)

        return MatchResult(
            matched_rules=matched_rules, category_matches=category_matches
        )

    def check_match(
        self,
        rule: Rule,
        data: BaseModel | dict,
    ) -> bool:
        """
        Determine if the value at the given path in data matches the expected value.

        Args:
            rule (Rule): A Rule object containing the path, expected match value, and
                matching configuration.
            data (BaseModel | dict): The data object or dict to retrieve the value from.

        Returns:
            bool: True if actual value matches expected value; False otherwise.
        """
        if (value := self.get_value(data, rule.path)) is None:
            return False
        match rule.semantic_similarity:
            case True:
                return self.check_semantic_match(value, rule.match)
            case False:
                return self.check_exact_match(value, rule.match)
            case _:
                logger.warning(
                    "Unexpected semantic_similarity value: %s", rule.semantic_similarity
                )
                return False

    def check_semantic_match(self, actual: str, expected: str) -> bool:
        """
        Check if two strings match semantically using embeddings.

        Splits multi-value strings (comma/semicolon/newline-delimited) so each
        segment is checked individually. This prevents extra context in a segment
        (e.g. "Currently on SAP, performance issues") from diluting the embedding
        and causing a miss against a short expected phrase like "Poor performance".

        Args:
            actual (str): The actual value from user data.
            expected (str): The expected value from the rule.

        Returns:
            bool: True if any segment's similarity is above threshold, False otherwise.
        """
        parts = [p.strip() for p in re.split(r"[,;\n]", actual) if p.strip()]
        if len(parts) > 1:
            return any(self._single_semantic_match(part, expected) for part in parts)
        return self._single_semantic_match(actual, expected)

    def _single_semantic_match(self, actual: str, expected: str) -> bool:
        """
        Check semantic similarity between a single actual string and an expected string.

        Args:
            actual (str): The actual value (a single segment) from user data.
            expected (str): The expected value from the rule.

        Returns:
            bool: True if similarity is above threshold, False otherwise.
        """
        logger.info("Using embedding matching for this rule")

        # Convert both actual and expected to embeddings
        actual_embedding = self.model.encode(actual, convert_to_tensor=True)
        expected_embedding = self.model.encode(expected, convert_to_tensor=True)

        # Calculate cosine similarity
        similarity = util.pytorch_cos_sim(actual_embedding, expected_embedding).item()
        logger.info(
            "Embedding similarity (%r vs %r): %.3f", actual, expected, similarity
        )
        result = similarity >= self.similarity_threshold
        logger.info("Match result based on embedding: %s", result)
        return result

    def check_exact_match(self, actual: Any, expected: Any) -> bool:
        """
        Check if two values match exactly.

        Args:
            actual (Any): The actual value from user data.
            expected (Any): The expected value from the rule.

        Returns:
            bool: True if values match, False otherwise.
        """
        # Handle dict with 'labels' key (multi-select responses)
        if isinstance(actual, dict) and "labels" in actual:
            actual = actual["labels"]
            logger.info("Extracted labels from dict: %s", actual)

        # Both are strings (exact match)
        if isinstance(actual, str) and isinstance(expected, str):
            result = actual.strip() == expected.strip()

        # Actual is a list, expected is a string (multi-select match)
        elif isinstance(actual, list) and isinstance(expected, str):
            result = expected in actual

        # Expected is a list (supporting list of valid expected values)
        elif isinstance(expected, list):
            result = actual in expected

        else:
            result = actual == expected

        logger.info("Match result: %s", result)
        return result

    def get_value(self, data: BaseModel | dict, path: str) -> Any | None:
        """
        Retrieve a nested attribute or dictionary key value from a Pydantic model or dict using a dot-separated path.

        Args:
            data (BaseModel | dict): The data source (Pydantic model or dict).
            path (str): Dot-separated path string indicating the nested attribute/key to retrieve.

        Returns:
            Any | None: The value found at the nested path, or None if any part of the path is missing.
        """
        parts = path.split(".")
        current = data
        for part in parts:
            if current is None:
                return None
            # Handle Pydantic model attribute or dict key
            if isinstance(current, BaseModel):
                current = getattr(current, part, None)
            elif isinstance(current, dict):
                current = current.get(part)
            else:
                # Unsupported type
                return None
        return current

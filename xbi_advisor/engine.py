"""Public library API — AdvisoryEngine wires RulesEngine and any LLMClient into a single advise() call."""

import inspect
from typing import Any, Protocol, runtime_checkable

from xbi_advisor.models.advisory_result import AdvisoryResult
from xbi_advisor.models.types import RuleMatchDict
from xbi_advisor.rules_engine import RulesEngine


@runtime_checkable
class LLMClient(Protocol):
    """Interface for sync LLM backends."""

    def complete(self, prompt: str) -> str:
        """Send prompt and return the completion as a string."""
        ...


@runtime_checkable
class AsyncLLMClient(Protocol):
    """Interface for async LLM backends. Use in FastAPI and other async contexts."""

    async def complete(self, prompt: str) -> str:
        """Send prompt and return the completion as a string."""
        ...


class StubLLMClient:
    """Credential-free sync LLM client for demos and tests."""

    def complete(self, prompt: str) -> str:
        return "stub recommendation"


class AsyncStubLLMClient:
    """Credential-free async LLM client for demos and tests."""

    async def complete(self, prompt: str) -> str:
        return "async stub recommendation"


class AdvisoryEngine:
    """
    Runs the full advisory pipeline: rules first, LLM last.

    Pass any LLMClient (or AsyncLLMClient for async use). The engine builds the
    prompt from matched rules — the LLM cannot invent findings, only explain them.
    """

    def __init__(
        self, rules_engine: RulesEngine, llm_client: LLMClient | AsyncLLMClient
    ) -> None:
        self.rules_engine = rules_engine
        self.llm_client: Any = llm_client  # LLMClient | AsyncLLMClient; Any avoids union/await type conflict at call sites

    def advise(self, user_input: dict[str, Any]) -> AdvisoryResult:
        """
        Run the full advisory pipeline: match rules, then generate recommendation.

        Args:
            user_input: Dict of user responses. Nested dicts use dot-path matching
                        in rules (e.g. path "data_governance.data_ownership").

        Returns:
            AdvisoryResult with matched rules and LLM-generated recommendation.

        Raises:
            TypeError: If called with an AsyncLLMClient. Use aadvise() instead.
        """
        if inspect.iscoroutinefunction(self.llm_client.complete):
            raise TypeError(
                f"advise() requires a sync LLMClient, got {type(self.llm_client).__name__} "
                "which is async. Use aadvise() instead."
            )
        match_result = self.rules_engine.match(user_input)
        prompt = self._build_prompt(match_result.matched_rules)
        recommendation = self.llm_client.complete(prompt)
        return AdvisoryResult(
            matched_rules=match_result.matched_rules,
            category_matches=match_result.category_matches,
            recommendation=recommendation,
        )

    async def aadvise(self, user_input: dict[str, Any]) -> AdvisoryResult:
        """
        Async variant of advise(). Use in FastAPI endpoints and other async contexts.

        The rules engine runs synchronously (CPU-bound, no I/O).
        Only the LLM call is awaited, keeping the event loop unblocked.

        Requires an AsyncLLMClient. Passing a sync LLMClient will raise TypeError.
        """
        if not inspect.iscoroutinefunction(self.llm_client.complete):
            raise TypeError(
                f"aadvise() requires a client with async complete(), "
                f"got {type(self.llm_client).__name__}.complete() which is synchronous. "
                "Use advise() for sync clients or pass an AsyncLLMClient."
            )
        match_result = self.rules_engine.match(user_input)
        prompt = self._build_prompt(match_result.matched_rules)
        recommendation = await self.llm_client.complete(prompt)  # type: ignore[misc]
        return AdvisoryResult(
            matched_rules=match_result.matched_rules,
            category_matches=match_result.category_matches,
            recommendation=recommendation,
        )

    def _build_prompt(self, matched_rules: list[RuleMatchDict]) -> str:
        if not matched_rules:
            return "No issues were detected. Summarise that the setup appears sound."

        rule_lines = "\n".join(
            f"- [{r['id']}] {r['recommendation']} (reason: {r['description']})"
            for r in matched_rules
        )
        return (
            "You are an expert advisor. Based on the following detected issues, "
            "write a concise, actionable advisory report:\n\n"
            f"{rule_lines}\n\n"
            "Be specific. Reference each issue by its ID. Prioritise by impact."
        )

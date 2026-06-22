from xbi_advisor.engine import AdvisoryEngine
from xbi_advisor.models.advisory_result import AdvisoryResult
from xbi_advisor.rules_engine import RulesEngine


def test_advise_returns_advisory_result(sample_rules_path, stub_llm_client):
    engine = AdvisoryEngine(
        rules_engine=RulesEngine.from_yaml(sample_rules_path),
        llm_client=stub_llm_client,
    )
    result = engine.advise({"data_governance": {"data_ownership": "no"}})
    assert isinstance(result, AdvisoryResult)


def test_advise_populates_recommendation(sample_rules_path, stub_llm_client):
    engine = AdvisoryEngine(
        rules_engine=RulesEngine.from_yaml(sample_rules_path),
        llm_client=stub_llm_client,
    )
    result = engine.advise({"data_governance": {"data_ownership": "no"}})
    assert result.recommendation == "stub recommendation"


def test_advise_populates_matched_rules(sample_rules_path, stub_llm_client):
    engine = AdvisoryEngine(
        rules_engine=RulesEngine.from_yaml(sample_rules_path),
        llm_client=stub_llm_client,
    )
    result = engine.advise({"data_governance": {"data_ownership": "no"}})
    assert len(result.matched_rules) == 1
    assert result.matched_rules[0]["id"] == "no_data_ownership"


def test_advise_with_no_matches(sample_rules_path, stub_llm_client):
    engine = AdvisoryEngine(
        rules_engine=RulesEngine.from_yaml(sample_rules_path),
        llm_client=stub_llm_client,
    )
    result = engine.advise({"data_governance": {"data_ownership": "yes"}})
    assert isinstance(result, AdvisoryResult)
    assert len(result.matched_rules) == 0
    assert result.recommendation == "stub recommendation"


def test_stub_llm_client_receives_prompt(sample_rules_path):
    received: list[str] = []

    class CapturingStub:
        def complete(self, prompt: str) -> str:
            received.append(prompt)
            return "captured"

    engine = AdvisoryEngine(
        rules_engine=RulesEngine.from_yaml(sample_rules_path),
        llm_client=CapturingStub(),
    )
    engine.advise({"data_governance": {"data_ownership": "no"}})
    assert len(received) == 1
    assert "no_data_ownership" in received[0]

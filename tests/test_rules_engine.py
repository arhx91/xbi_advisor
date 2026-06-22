import pytest

from xbi_advisor.models.match_result import MatchResult
from xbi_advisor.rules_engine import RulesEngine


def test_match_returns_match_result(sample_rules_path):
    engine = RulesEngine.from_yaml(sample_rules_path)
    user_input = {"data_governance": {"data_ownership": "no"}}
    result = engine.match(user_input)
    assert isinstance(result, MatchResult)


def test_match_result_has_matched_rules(sample_rules_path):
    engine = RulesEngine.from_yaml(sample_rules_path)
    user_input = {"data_governance": {"data_ownership": "no"}}
    result = engine.match(user_input)
    assert len(result.matched_rules) == 1
    assert result.matched_rules[0]["id"] == "no_data_ownership"


def test_match_result_has_category_matches(sample_rules_path):
    engine = RulesEngine.from_yaml(sample_rules_path)
    user_input = {"data_governance": {"data_ownership": "no"}}
    result = engine.match(user_input)
    assert "data_governance" in result.category_matches
    assert len(result.category_matches["data_governance"]) == 1


def test_no_match_returns_empty_result(sample_rules_path):
    engine = RulesEngine.from_yaml(sample_rules_path)
    user_input = {"data_governance": {"data_ownership": "yes"}}
    result = engine.match(user_input)
    assert isinstance(result, MatchResult)
    assert len(result.matched_rules) == 0
    assert result.category_matches == {}


def test_model_loaded_only_once(sample_rules_path):
    """Two RulesEngine instances with the same model name share one loaded model."""
    engine_a = RulesEngine.from_yaml(sample_rules_path)
    engine_b = RulesEngine.from_yaml(sample_rules_path)
    assert engine_a.model is engine_b.model


def test_exact_match_string(sample_rules_path):
    engine = RulesEngine.from_yaml(sample_rules_path)
    result = engine.match({"data_governance": {"data_ownership": "no"}})
    ids = [r["id"] for r in result.matched_rules]
    assert "no_data_ownership" in ids


def test_exact_match_miss(sample_rules_path):
    engine = RulesEngine.from_yaml(sample_rules_path)
    result = engine.match({"data_governance": {"data_ownership": "yes"}})
    ids = [r["id"] for r in result.matched_rules]
    assert "no_data_ownership" not in ids


def test_semantic_match_similar_phrase(sample_rules_path):
    """Semantically similar phrase should match a semantic_similarity: true rule."""
    engine = RulesEngine.from_yaml(sample_rules_path)
    result = engine.match(
        {"maturity_level": {"bi_usage": "we hardly ever use BI tools"}}
    )
    ids = [r["id"] for r in result.matched_rules]
    assert "infrequent_bi_usage" in ids


def test_semantic_match_dissimilar_phrase(sample_rules_path):
    """Semantically unrelated phrase should not match a semantic_similarity: true rule."""
    engine = RulesEngine.from_yaml(sample_rules_path)
    result = engine.match(
        {"maturity_level": {"bi_usage": "we use dashboards intensively every day"}}
    )
    ids = [r["id"] for r in result.matched_rules]
    assert "infrequent_bi_usage" not in ids


@pytest.mark.asyncio
async def test_aadvise_raises_with_sync_client(sample_rules_path):
    """aadvise() must raise TypeError when called with a sync LLMClient."""
    import pytest

    from xbi_advisor.engine import AdvisoryEngine, StubLLMClient

    engine = AdvisoryEngine(
        rules_engine=RulesEngine.from_yaml(sample_rules_path),
        llm_client=StubLLMClient(),
    )
    with pytest.raises(TypeError, match="async complete\\(\\)"):
        await engine.aadvise({"data_governance": {"data_ownership": "no"}})

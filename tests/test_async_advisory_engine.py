import pytest

from xbi_advisor.engine import AdvisoryEngine, AsyncLLMClient, AsyncStubLLMClient
from xbi_advisor.models.advisory_result import AdvisoryResult
from xbi_advisor.rules_engine import RulesEngine


@pytest.mark.asyncio
async def test_aadvise_returns_advisory_result(sample_rules_path):
    engine = AdvisoryEngine(
        rules_engine=RulesEngine.from_yaml(sample_rules_path),
        llm_client=AsyncStubLLMClient(),
    )
    result = await engine.aadvise({"data_governance": {"data_ownership": "no"}})
    assert isinstance(result, AdvisoryResult)


@pytest.mark.asyncio
async def test_aadvise_populates_recommendation(sample_rules_path):
    engine = AdvisoryEngine(
        rules_engine=RulesEngine.from_yaml(sample_rules_path),
        llm_client=AsyncStubLLMClient(),
    )
    result = await engine.aadvise({"data_governance": {"data_ownership": "no"}})
    assert result.recommendation == "async stub recommendation"


@pytest.mark.asyncio
async def test_async_stub_satisfies_protocol(sample_rules_path):
    stub = AsyncStubLLMClient()
    assert isinstance(stub, AsyncLLMClient)

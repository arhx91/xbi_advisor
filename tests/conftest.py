from pathlib import Path

import pytest

from xbi_advisor.engine import StubLLMClient

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_rules_path() -> Path:
    return FIXTURES / "sample_rules.yaml"


@pytest.fixture
def stub_llm_client() -> StubLLMClient:
    return StubLLMClient()

"""Guard for the manual-mode example fixture.

`run_advisor(manual=True)` (the /test-pdf endpoint and `python -m xbi_advisor
--manual`) loads examples/manual_responses.json. This test keeps that fixture
aligned with question_mapping.json: if a question title drifts, the fixture's
answer key stops matching and a category falls empty — caught here.
"""

import json
from pathlib import Path

from ruamel.yaml import YAML

from xbi_advisor.export_typeform_responses import process_typeform_responses

MANUAL_FIXTURE = Path("examples/manual_responses.json")
QUESTION_MAPPING = Path("xbi_advisor/assets/templates/question_mapping.json")
EXPECTED_CATEGORIES = [
    "user_info",
    "ecosystem",
    "security",
    "data_governance",
    "maturity_level",
    "capabilities",
    "pricing",
]


def test_manual_fixture_maps_to_complete_profile(tmp_path):
    assert MANUAL_FIXTURE.exists(), f"manual fixture missing: {MANUAL_FIXTURE}"

    responses = json.loads(MANUAL_FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(responses, list) and responses, "fixture must be a non-empty list"

    out = tmp_path / "user_input"
    process_typeform_responses(responses, out, QUESTION_MAPPING)
    profile = YAML(typ="safe").load((out / "user_input.yaml").read_text())

    empty = [c for c in EXPECTED_CATEGORIES if not profile.get(c)]
    assert not empty, (
        f"manual fixture leaves categories empty (titles drifted?): {empty}"
    )

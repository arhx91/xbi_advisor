"""Production-flow regression guard for the Typeform -> profile -> merge transform.

This exercises the real pipeline step that produced the user-input contamination
bug: a client's responses are written to the runtime tmp dir, then merged with the
real assets directory. A client must never inherit answers they did not give.

No network/LLM/PDF here — those are downstream of the data merge.
"""

from pathlib import Path

from xbi_advisor.export_typeform_responses import process_typeform_responses
from xbi_advisor.parser import get_flattened_content

ASSETS_DIR = Path("xbi_advisor/assets")
QUESTION_MAPPING_FILE = ASSETS_DIR / "templates" / "question_mapping.json"


def test_minimal_client_does_not_inherit_assets_example(tmp_path, monkeypatch):
    """A client who answers only identity questions inherits no other answers."""
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("TMP_DIR", str(runtime))

    responses = [
        {
            "response_id": "test123",
            "submitted_at": "2026-06-22T10:00:00Z",
            "answers": {
                "What is your name?": "Bob",
                "What is your email address?": "bob@acme.com",
                "What is the name of your organization?": "Acme",
            },
        }
    ]
    process_typeform_responses(responses, runtime / "user_input", QUESTION_MAPPING_FILE)

    combined = get_flattened_content(ASSETS_DIR)

    # The client's own answers are present.
    assert combined["user_info"]["name"] == "Bob"
    assert combined["user_info"]["email"] == "bob@acme.com"
    assert combined["user_info"]["organization_name"] == "Acme"

    # Categories the client did not answer carry no inherited values from the
    # committed assets/user_input example.
    assert "migration" not in combined.get("ecosystem", {})
    assert "centralized_governance" not in combined.get("data_governance", {})
    assert "user_licensing" not in combined.get("pricing", {})

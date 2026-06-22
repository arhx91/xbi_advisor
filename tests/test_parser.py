"""Tests for parser asset/runtime separation.

The parser merges static config from the assets directory with the per-run user
input written to the runtime tmp directory. The committed assets/user_input
example must never enter the merge — doing so leaks a prior respondent's answers
into every report.
"""

import textwrap
from pathlib import Path

from xbi_advisor.parser import get_flattened_content


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def test_assets_user_input_excluded_from_merge(tmp_path, monkeypatch):
    """assets/user_input is excluded; runtime user_input and static config load."""
    assets = tmp_path / "assets"

    # Committed example under assets/user_input — must be ignored by the merge.
    _write(
        assets / "user_input" / "user_input.yaml",
        """
        user_info:
          name: STALE
          email: stale@example.com
        ecosystem:
          migration: STALE_MIGRATION
        """,
    )

    # Static config that MUST still be loaded from assets.
    _write(
        assets / "properties" / "config.yaml",
        """
        static_config:
          foo: bar
        """,
    )

    # Real per-run user input lives in the runtime tmp dir.
    runtime = tmp_path / "runtime"
    _write(
        runtime / "user_input" / "user_input.yaml",
        """
        user_info:
          name: REAL
        """,
    )
    monkeypatch.setenv("TMP_DIR", str(runtime))

    combined = get_flattened_content(assets)

    # Real runtime data is present.
    assert combined["user_info"]["name"] == "REAL"
    # Stale-only fields from the assets example never leak in.
    assert "email" not in combined.get("user_info", {})
    assert "migration" not in combined.get("ecosystem", {})
    # Static config is still merged.
    assert combined["static_config"]["foo"] == "bar"


def test_runtime_user_input_still_loaded_without_assets_copy(tmp_path, monkeypatch):
    """Runtime user_input loads even when no assets/user_input directory exists."""
    assets = tmp_path / "assets"
    _write(
        assets / "properties" / "config.yaml",
        """
        static_config:
          foo: bar
        """,
    )

    runtime = tmp_path / "runtime"
    _write(
        runtime / "user_input" / "user_input.yaml",
        """
        user_info:
          name: REAL
          email: real@example.com
        """,
    )
    monkeypatch.setenv("TMP_DIR", str(runtime))

    combined = get_flattened_content(assets)

    assert combined["user_info"]["name"] == "REAL"
    assert combined["user_info"]["email"] == "real@example.com"
    assert combined["static_config"]["foo"] == "bar"

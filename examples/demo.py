"""
End-to-end demo of the xbi-advisor advisory engine.

Uses StubLLMClient — no cloud credentials required.

Run with:
    uv run python examples/demo.py
"""

from pathlib import Path

from xbi_advisor import AdvisoryEngine, RulesEngine, StubLLMClient

RULES_PATH = (
    Path(__file__).parent.parent / "xbi_advisor" / "assets" / "rules" / "rules.yaml"
)


def main() -> None:
    print("=== xbi-advisor demo ===\n")
    print("Initialising rules engine...")
    rules_engine = RulesEngine.from_yaml(str(RULES_PATH))
    print(f"Loaded {len(rules_engine.rules)} rules.\n")

    engine = AdvisoryEngine(
        rules_engine=rules_engine,
        llm_client=StubLLMClient(),
    )

    # Simulated user responses — field paths and values match the production rules in rules.yaml
    user_input = {
        "ecosystem": {
            "current_bi_tool": "Power BI",
            "platform": "Microsoft Azure",
        },
        "security": {
            "row_level_security": "Yes, RLS is essential for our BI setup",
        },
        "data_governance": {
            "version_control": "Yes, these features are essential for our team",
        },
        "maturity_level": {
            "data_literacy": "Advanced: Team members are comfortable working with data, can perform basic analysis, and understand key statistical concepts",
            "code_first_approach": "We mix both - some reports are built with code, others with drag-and-drop (25–50%)",
        },
        "pricing": {
            "user_licensing": "Moderately important: Cost is considered, but it's balanced with features and other factors",
        },
    }

    print("Running advisory engine on sample input...")
    result = engine.advise(user_input)

    print(f"\nMatched {len(result.matched_rules)} rules:")
    for rule in result.matched_rules:
        print(f"  [{rule['id']}] {rule['recommendation']}")

    print(f"\nAdvisory output:\n{result.recommendation}")
    print("\nFor a real advisory output, see: examples/sample_report.md")
    print("\n=== demo complete ===")


if __name__ == "__main__":
    main()

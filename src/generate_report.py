from pathlib import Path
import os
import pandas as pd


def load_analysis_results(base_dir: Path):
    """Load deterministic analysis results created by Python/Rules."""

    exception_path = base_dir / "results" / "exception_summary.csv"
    repeated_path = base_dir / "results" / "repeated_loss_summary.csv"

    exceptions = pd.read_csv(exception_path)
    repeated = pd.read_csv(repeated_path)

    return exceptions, repeated


def build_evidence(
    exceptions: pd.DataFrame,
    repeated: pd.DataFrame
) -> str:
    """Convert verified analysis results into evidence for the LLM."""

    repeated_text = repeated[
        [
            "product_code",
            "exception_reason",
            "occurrence_count",
            "priority",
        ]
    ].to_string(index=False)

    evidence = f"""
PRODUCTION ANALYSIS EVIDENCE

Total exception records: {len(exceptions)}

Repeated loss patterns:
{repeated_text}

Important constraints:
- The dataset contains KPI-level production information.
- KPI values were calculated by Python.
- Exception status and priority were determined by fixed rules.
- The data does NOT prove physical root causes.
- Root causes must not be invented.
""".strip()

    return evidence


def build_prompt(evidence: str) -> str:
    """Build a constrained production-management reporting prompt."""

    return f"""
You are assisting a production manager.

Analyze ONLY the evidence supplied below.

Tasks:
1. Summarize the most important production issue.
2. Identify the highest-priority repeated pattern.
3. State the evidence supporting that priority.
4. Recommend which data should be checked next.
5. Clearly distinguish observed facts from hypotheses.

Rules:
- Do not invent root causes.
- Do not invent production conditions.
- Do not recalculate KPI values.
- Do not change the supplied priority levels.
- Use only the supplied evidence.
- If the evidence is insufficient, explicitly state that.

{evidence}

Return the report using exactly these sections:

## Production Summary
## Priority Issue
## Evidence
## Recommended Next Check
## Limitations
""".strip()


def call_llm(prompt: str) -> str:
    """Generate the management report with the OpenAI Responses API."""

    from openai import OpenAI

    client = OpenAI()

    model = os.getenv(
        "OPENAI_MODEL",
        "gpt-5.6-luna"
    )

    response = client.responses.create(
        model=model,
        input=prompt,
    )

    return response.output_text


def main():
    base_dir = Path(__file__).resolve().parent.parent

    exceptions, repeated = load_analysis_results(base_dir)

    evidence = build_evidence(exceptions, repeated)
    prompt = build_prompt(evidence)

    print("\n=== Evidence passed to LLM ===\n")
    print(evidence)

    if not os.getenv("OPENAI_API_KEY"):
        print("\n=== DRY RUN ===")
        print("OPENAI_API_KEY is not configured.")
        print("No API request was made.")
        return

    report = call_llm(prompt)

    output_path = (
        base_dir
        / "results"
        / "production_report.md"
    )

    output_path.write_text(
        report,
        encoding="utf-8"
    )

    print("\n=== LLM Production Report ===\n")
    print(report)

    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()
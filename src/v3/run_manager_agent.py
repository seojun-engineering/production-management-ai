from pathlib import Path
from typing import Literal
import json
import os

import pandas as pd
from openai import OpenAI
from pydantic import BaseModel


# ==================================================
# 1. STRUCTURED OUTPUT SCHEMA
# ==================================================

class ReviewTarget(BaseModel):
    rank: int
    target: str
    target_type: Literal[
        "production_date",
        "time_window",
        "downtime_event_group",
        "data_quality",
    ]
    supporting_agents: list[str]
    evidence: list[str]
    reason_for_review: str
    recommended_next_check: str


class CrossAgentAgreement(BaseModel):
    topic: str
    agents: list[str]
    shared_observation: str


class EvidenceConflict(BaseModel):
    topic: str
    observations: list[str]
    interpretation: str


class ManagerOutput(BaseModel):
    executive_summary: str

    overall_review_priority: Literal[
        "LOW",
        "MEDIUM",
        "HIGH",
    ]

    top_review_targets: list[ReviewTarget]

    cross_agent_agreements: list[CrossAgentAgreement]

    evidence_conflicts_or_tensions: list[EvidenceConflict]

    data_quality_constraints: list[str]

    unknowns: list[str]

    recommended_next_data: list[str]

    root_cause_status: Literal[
        "NOT_ESTABLISHED"
    ]

    evidence_sufficiency: Literal[
        "LOW",
        "MEDIUM",
        "HIGH",
    ]

    evidence_sufficiency_reason: str


# ==================================================
# 2. HELPERS
# ==================================================

def load_json(path: Path):
    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


def save_json(data, path: Path):
    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# ==================================================
# 3. VERIFIED PYTHON CONTEXT
# ==================================================

def build_verified_context(
    base_dir: Path,
) -> dict:

    results_dir = (
        base_dir
        / "results"
    )

    daily = pd.read_csv(
        results_dir
        / "v2_daily_kpi_screening.csv"
    )

    duration_groups = pd.read_csv(
        results_dir
        / "v2_downtime_duration_groups.csv"
    )

    outliers = pd.read_csv(
        results_dir
        / "v2_outlier_days.csv"
    )

    ranked = (
        daily[
            daily["screening_rank"].notna()
        ]
        .sort_values(
            "screening_rank"
        )
        .head(5)
    )

    top_days = []

    for _, row in ranked.iterrows():

        top_days.append(
            {
                "date": row["date"],
                "screening_rank": int(
                    row["screening_rank"]
                ),
                "screening_score": float(
                    row["screening_score"]
                ),
                "operating_ratio": float(
                    row["operating_ratio"]
                ),
                "downtime_h": float(
                    row["downtime_h"]
                ),
                "event_count": int(
                    row["event_count"]
                ),
            }
        )

    long_group = (
        duration_groups[
            duration_groups[
                "duration_group"
            ].astype(str).str.contains(
                "Long"
            )
        ]
        .iloc[0]
    )

    return {
        "python_verified_top_5_days":
            top_days,

        "python_verified_long_event_group": {
            "event_count": int(
                long_group[
                    "event_count"
                ]
            ),
            "event_share_pct": float(
                long_group[
                    "event_share_pct"
                ]
            ),
            "duration_share_pct": float(
                long_group[
                    "duration_share_pct"
                ]
            ),
        },

        "python_verified_outlier_days":
            outliers.to_dict(
                orient="records"
            ),

        "important_definitions": {
            "operating_ratio":
                "operation_time / monitored_time",

            "screening_score":
                (
                    "Relative equal-weight percentile "
                    "screening metric. It is NOT a "
                    "plant control limit."
                ),

            "hourly_downtime":
                (
                    "Downtime derived from the verified "
                    "hourly operation table."
                ),

            "event_log_duration":
                (
                    "Diagnostic event-log duration. "
                    "It is NOT canonical equipment downtime."
                ), 
        },

        "verified_data_quality_details": {
            "missing_hourly_date": "2022-09-22",
            "corrected_downtime_date": {
                "source_date": "2022-01-13",
                "corrected_date": "2023-01-13",
                "corrected_rows": 18
            }
        },
    }


# ==================================================
# 4. MANAGER PROMPT
# ==================================================

MANAGER_RULES = """
You are the Production Manager Agent in an
evidence-grounded manufacturing decision-support system.

You receive:

1. Structured outputs from four specialist agents.
2. A compact set of Python-verified facts.

Your task is NOT to invent a root cause.

Your task is to decide:
- what should be reviewed first,
- why it deserves review,
- where specialist evidence agrees,
- where evidence differs,
- what data must be obtained next.

STRICT RULES:

1. Python-verified facts have higher authority than
   specialist narrative.

2. Do not recalculate KPI values.

3. Do not change Python-generated screening ranks.

4. Do not interpret multiple agents mentioning the
   same target as proof of causation.

5. Cross-agent agreement can strengthen REVIEW priority,
   but it must NOT strengthen causal confidence.

6. Never state that product type caused performance loss.

7. Never state that a downtime event was a machine failure
   unless the evidence explicitly proves this.

8. Distinguish:
   - hourly-record downtime
   - event-log duration

9. Event start counts by hour are raw counts.
   Do not treat them as normalized occurrence rates unless
   exposure by hour has been validated.

10. Do not describe operating ratio as OEE.

11. Specialist confidence values are uncalibrated model
    self-assessments. Do NOT use them as probabilities or
    ranking weights.

12. Root cause status MUST remain NOT_ESTABLISHED.

13. Recommended actions must be evidence checks,
    data requests, validation tasks, or review priorities.
    Do not recommend physical maintenance actions without
    causal evidence.

14. Prefer a small number of high-value review targets
    over a long generic list.

15. A supporting agent may be listed only when that agent
    explicitly provided evidence for that review target.

16. Do not call something a cross-agent agreement unless
    at least two specialist agents explicitly reported
    the same observation.

17. Hour-of-day patterns such as 12-16 should use
    target_type = "time_window".
"""


# ==================================================
# 5. RUN MANAGER
# ==================================================

def run_manager(
    client: OpenAI,
    model: str,
    specialists: dict,
    verified_context: dict,
) -> ManagerOutput:

    prompt = f"""
{MANAGER_RULES}

PYTHON-VERIFIED CONTEXT:

{json.dumps(
    verified_context,
    ensure_ascii=False,
    indent=2,
)}

SPECIALIST AGENT OUTPUTS:

{json.dumps(
    specialists,
    ensure_ascii=False,
    indent=2,
)}

Produce the final Production Manager analysis.

For top_review_targets:
- rank them in review order,
- use only evidence supplied above,
- include the specialist agents that support each target,
- explicitly state what should be checked next.

For evidence_conflicts_or_tensions:
include cases such as:
- statistical outlier vs operational screening rank,
- frequency vs duration,
- raw temporal counts vs missing exposure normalization,
- product association vs lack of causal evidence.

For supporting_agents and cross_agent_agreements:
only include an agent when that specialist explicitly
provided evidence for the same target or observation.
""".strip()

    response = client.responses.parse(
        model=model,
        input=prompt,
        text_format=ManagerOutput,
    )

    for output in response.output:

        if output.type != "message":
            continue

        for content in output.content:

            if content.type != "output_text":
                continue

            if content.parsed is not None:
                return content.parsed

    raise RuntimeError(
        "No parsed Manager output returned."
    )


# ==================================================
# 6. MARKDOWN REPORT
# ==================================================

def build_markdown(
    result: ManagerOutput,
) -> str:

    lines = []

    lines.append(
        "# V3 Multi-Agent Production Action Report"
    )

    lines.append("")

    lines.append(
        "## Executive Summary"
    )

    lines.append("")

    lines.append(
        result.executive_summary
    )

    lines.append("")

    lines.append(
        f"**Overall Review Priority:** "
        f"{result.overall_review_priority}"
    )

    lines.append("")

    lines.append(
        f"**Root Cause Status:** "
        f"{result.root_cause_status}"
    )

    lines.append("")

    lines.append(
        "## Top Review Targets"
    )

    lines.append("")

    for target in sorted(
        result.top_review_targets,
        key=lambda x: x.rank,
    ):

        lines.append(
            f"### {target.rank}. "
            f"{target.target}"
        )

        lines.append("")

        lines.append(
            f"- Type: {target.target_type}"
        )

        lines.append(
            "- Supporting Agents: "
            + ", ".join(
                target.supporting_agents
            )
        )

        lines.append(
            f"- Reason: "
            f"{target.reason_for_review}"
        )

        lines.append(
            f"- Next Check: "
            f"{target.recommended_next_check}"
        )

        lines.append(
            "- Evidence:"
        )

        for evidence in target.evidence:
            lines.append(
                f"  - {evidence}"
            )

        lines.append("")

    lines.append(
        "## Cross-Agent Agreements"
    )

    lines.append("")

    for item in result.cross_agent_agreements:

        lines.append(
            f"- **{item.topic}** "
            f"({', '.join(item.agents)}): "
            f"{item.shared_observation}"
        )

    lines.append("")

    lines.append(
        "## Evidence Conflicts / Tensions"
    )

    lines.append("")

    for item in (
        result.evidence_conflicts_or_tensions
    ):

        lines.append(
            f"### {item.topic}"
        )

        for observation in item.observations:
            lines.append(
                f"- {observation}"
            )

        lines.append(
            f"- Interpretation: "
            f"{item.interpretation}"
        )

        lines.append("")

    lines.append(
        "## Data Quality Constraints"
    )

    lines.append("")

    for item in (
        result.data_quality_constraints
    ):
        lines.append(
            f"- {item}"
        )

    lines.append("")

    lines.append(
        "## Unknowns"
    )

    lines.append("")

    for item in result.unknowns:
        lines.append(
            f"- {item}"
        )

    lines.append("")

    lines.append(
        "## Recommended Next Data"
    )

    lines.append("")

    for item in (
        result.recommended_next_data
    ):
        lines.append(
            f"- {item}"
        )

    lines.append("")

    lines.append(
        "## Evidence Sufficiency"
    )

    lines.append("")

    lines.append(
        f"**{result.evidence_sufficiency}**"
    )

    lines.append("")

    lines.append(
        result.evidence_sufficiency_reason
    )

    lines.append("")

    return "\n".join(lines)


# ==================================================
# 7. MAIN
# ==================================================

def main():

    base_dir = Path(
        __file__
    ).resolve().parents[2]

    agents_dir = (
        base_dir
        / "results"
        / "v3"
        / "agents"
    )

    output_dir = (
        base_dir
        / "results"
        / "v3"
    )

    if not os.getenv(
        "OPENAI_API_KEY"
    ):
        raise RuntimeError(
            "OPENAI_API_KEY is not configured."
        )

    specialist_path = (
        agents_dir
        / "all_specialist_outputs.json"
    )

    specialists = load_json(
        specialist_path
    )

    verified_context = (
        build_verified_context(
            base_dir
        )
    )

    model = os.getenv(
        "OPENAI_MODEL",
        "gpt-5.6-luna",
    )

    client = OpenAI()

    print(
        "\n"
        + "=" * 70
    )

    print(
        "V3 PRODUCTION MANAGER AGENT"
    )

    print(
        "=" * 70
    )

    print(
        f"\nModel: {model}"
    )

    result = run_manager(
        client=client,
        model=model,
        specialists=specialists,
        verified_context=verified_context,
    )

    json_path = (
        output_dir
        / "manager_analysis.json"
    )

    markdown_path = (
        output_dir
        / "production_action_report.md"
    )

    save_json(
        result.model_dump(),
        json_path,
    )

    markdown_report = (
        build_markdown(result)
    )

    markdown_path.write_text(
        markdown_report,
        encoding="utf-8",
    )

    print(
        "\nOverall Review Priority:",
        result.overall_review_priority,
    )

    print(
        "Root Cause Status:",
        result.root_cause_status,
    )

    print(
        "Evidence Sufficiency:",
        result.evidence_sufficiency,
    )

    print(
        "\nTop Review Targets:"
    )

    for target in sorted(
        result.top_review_targets,
        key=lambda x: x.rank,
    ):

        print(
            f"{target.rank}. "
            f"{target.target}"
            f" [{target.target_type}]"
        )

    print(
        f"\nJSON saved: "
        f"{json_path}"
    )

    print(
        f"Report saved: "
        f"{markdown_path}"
    )


if __name__ == "__main__":
    main()
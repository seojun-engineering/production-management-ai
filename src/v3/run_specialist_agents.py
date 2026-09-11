from pathlib import Path
from typing import Literal
import json
import os

from openai import OpenAI
from pydantic import BaseModel, Field


# ==================================================
# 1. STRUCTURED OUTPUT SCHEMA
# ==================================================

class Finding(BaseModel):
    observation: str
    evidence_reference: str
    why_it_matters: str


class SpecialistOutput(BaseModel):
    agent: Literal[
        "production",
        "downtime",
        "efficiency",
        "pattern",
    ]

    summary: str

    review_priority: Literal[
        "LOW",
        "MEDIUM",
        "HIGH",
    ]

    key_findings: list[Finding]

    unknowns: list[str]

    recommended_next_checks: list[str]

    confidence: float = Field(
        ge=0.0,
        le=1.0
    )


# ==================================================
# 2. AGENT INSTRUCTIONS
# ==================================================

AGENT_INSTRUCTIONS = {
    "production": """
You are the Production Agent in a manufacturing
decision-support system.

Your scope:
- production output
- screening-ranked production days
- product-level observations
- operating performance relevant to production review

Do not analyze physical root causes.

Focus on:
1. Which production days deserve review.
2. What numerical evidence supports that review.
3. What information a production manager should check next.
""",

    "downtime": """
You are the Downtime Agent in a manufacturing
decision-support system.

Your scope:
- downtime event frequency
- downtime event duration
- long-duration event concentration
- statistical downtime outliers

Important:
Event-log duration is diagnostic evidence.
It is NOT canonical equipment downtime.

Do not claim that an event represents a machine failure
unless the evidence explicitly says so.
""",

    "efficiency": """
You are the Efficiency Agent in a manufacturing
decision-support system.

Your scope:
- operating ratio
- operating loss
- low-operating-ratio production days
- product-level efficiency observations

Operating Ratio means:
operation time / monitored time.

Do NOT call it OEE.

Do not claim that product type caused efficiency differences.
""",

    "pattern": """
You are the Pattern Agent in a manufacturing
decision-support system.

Your scope:
- hour-of-day patterns
- weekday patterns
- repeated temporal patterns
- downtime-event start-time patterns

Your task is to identify repeated associations.

Do not describe correlation as causation.
Do not invent shift schedules, worker behavior,
equipment conditions, or production policies.
""",
}


# ==================================================
# 3. COMMON GUARDRAILS
# ==================================================

COMMON_RULES = """
You are one specialist component of an
evidence-grounded multi-agent production analysis system.

STRICT RULES:

1. Use ONLY the supplied evidence JSON.
2. Do not invent data.
3. Do not calculate new KPI values.
4. Do not change Python-generated rankings.
5. Do not invent root causes.
6. Distinguish observation from hypothesis.
7. If evidence is insufficient, state that explicitly.
8. Recommended next checks are requests for additional
   evidence, not conclusions.
9. review_priority is your specialist review priority,
   not a plant control limit.
10. Every key finding must point to an identifiable
    field, record, table, date, percentile, or summary
    contained in the supplied evidence.
"""


# ==================================================
# 4. FILE HELPERS
# ==================================================

def load_json(path: Path):
    with path.open(
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)


def save_json(data, path: Path):
    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


# ==================================================
# 5. RUN ONE SPECIALIST
# ==================================================

def run_specialist(
    client: OpenAI,
    agent_name: str,
    evidence: dict,
    model: str,
) -> SpecialistOutput:

    prompt = f"""
{COMMON_RULES}

SPECIALIST ROLE:

{AGENT_INSTRUCTIONS[agent_name]}

Your required agent field must be:
{agent_name}

EVIDENCE JSON:

{json.dumps(
    evidence,
    ensure_ascii=False,
    indent=2
)}
""".strip()

    response = client.responses.parse(
        model=model,
        input=prompt,
        text_format=SpecialistOutput,
    )

    # Extract parsed structured output
    for output in response.output:

        if output.type != "message":
            continue

        for content in output.content:

            if content.type != "output_text":
                continue

            if content.parsed is not None:
                result = content.parsed

                # Extra validation:
                # model must identify itself correctly.
                if result.agent != agent_name:
                    raise ValueError(
                        f"Agent mismatch: "
                        f"expected {agent_name}, "
                        f"received {result.agent}"
                    )

                return result

    raise RuntimeError(
        f"No parsed output returned "
        f"for {agent_name} agent."
    )


# ==================================================
# 6. MAIN
# ==================================================

def main():
    base_dir = Path(
        __file__
    ).resolve().parents[2]

    evidence_dir = (
        base_dir
        / "results"
        / "v3"
        / "evidence"
    )

    output_dir = (
        base_dir
        / "results"
        / "v3"
        / "agents"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    if not os.getenv(
        "OPENAI_API_KEY"
    ):
        raise RuntimeError(
            "OPENAI_API_KEY is not configured."
        )

    model = os.getenv(
        "OPENAI_MODEL",
        "gpt-5.6-luna"
    )

    client = OpenAI()

    agents = [
        "production",
        "downtime",
        "efficiency",
        "pattern",
    ]

    print(
        "\n"
        + "=" * 70
    )

    print(
        "V3 SPECIALIST AGENTS"
    )

    print(
        "=" * 70
    )

    print(
        f"\nModel: {model}"
    )

    results = {}

    for agent_name in agents:

        evidence_path = (
            evidence_dir
            / f"{agent_name}_evidence.json"
        )

        if not evidence_path.exists():

            raise FileNotFoundError(
                f"Evidence file missing: "
                f"{evidence_path}"
            )

        print(
            f"\nRunning "
            f"{agent_name.upper()} Agent..."
        )

        evidence = load_json(
            evidence_path
        )

        result = run_specialist(
            client=client,
            agent_name=agent_name,
            evidence=evidence,
            model=model,
        )

        result_dict = (
            result.model_dump()
        )

        output_path = (
            output_dir
            / f"{agent_name}_analysis.json"
        )

        save_json(
            result_dict,
            output_path
        )

        results[
            agent_name
        ] = result_dict

        print(
            f"Priority: "
            f"{result.review_priority}"
        )

        print(
            f"Confidence: "
            f"{result.confidence:.2f}"
        )

        print(
            f"Saved: {output_path}"
        )

    # ==================================================
    # 7. COMBINED SPECIALIST OUTPUT
    # ==================================================

    combined_path = (
        output_dir
        / "all_specialist_outputs.json"
    )

    save_json(
        results,
        combined_path
    )

    print(
        "\n"
        + "=" * 70
    )

    print(
        "SPECIALIST AGENTS COMPLETE"
    )

    print(
        "=" * 70
    )

    print(
        f"\nAgents completed: "
        f"{len(results)}"
    )

    print(
        f"Combined output: "
        f"{combined_path}"
    )


if __name__ == "__main__":
    main()
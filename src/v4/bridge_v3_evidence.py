
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "v4"))

from evidence_validation import registry, validate

TARGET_DATE = "2022-11-03"

METRICS_TO_CHECK = {
    "screening_rank": "rank",
    "screening_score": "relative_score",
    "operating_ratio": "ratio",
    "downtime_h": "hourly_record_hours",
    "event_count": "events",
}


def main():
    manager_path = ROOT / "results/v3/manager_analysis.json"
    output_path = ROOT / "results/v4/v3_bridge_demo.json"

    manager = json.loads(
        manager_path.read_text(encoding="utf-8")
    )

    targets = manager["top_review_targets"]

    matches = [
        target for target in targets
        if target["target_type"] == "production_date"
        and target["target"] == TARGET_DATE
    ]

    if len(matches) != 1:
        raise ValueError(
            "Expected exactly one Manager target "
            f"for {TARGET_DATE}; found {len(matches)}"
        )

    target = matches[0]
    evidence_id = f"V2-DAILY-{TARGET_DATE}"

    indexed = registry(ROOT)

    if evidence_id not in indexed:
        raise ValueError(
            f"Evidence not found: {evidence_id}"
        )

    record = indexed[evidence_id]

    if record["kind"] != "daily":
        raise ValueError("Expected daily evidence")

    row = record["row"]

    claims = []

    for metric, unit in METRICS_TO_CHECK.items():
        claim = {
            "evidence_id": evidence_id,
            "metric": metric,
            "value": float(row[metric]),
            "unit": unit,
            "aggregation": "daily",
            "date": TARGET_DATE,
        }

        if metric == "screening_rank":
            claim["selection_rule"] = "screening_top_5"

        claims.append(claim)

    results = [
        validate(claim, indexed)
        for claim in claims
    ]

    all_passed = all(
        result["passed"] for result in results
    )

    output = {
        "review_id": "V4-REVIEW-2022-11-03",
        "source": "V3 Manager target + V2 Python evidence",
        "target_date": TARGET_DATE,
        "target_type": target["target_type"],
        "manager_review_rank": target["rank"],
        "manager_rank_validated": False,
        "supporting_agents": target["supporting_agents"],
        "evidence_id": evidence_id,
        "root_cause_status": "NOT_ESTABLISHED",
        "factual_claims": claims,
        "validation_results": results,
        "all_factual_claims_passed": all_passed,
        "legacy_manager_narrative": {
            "evidence": target["evidence"],
            "reason_for_review": target["reason_for_review"],
            "recommended_next_check": target[
                "recommended_next_check"
            ],
            "validation_status": "HUMAN_REVIEW_REQUIRED",
        },
        "limitations": [
            "Factual values were retrieved from V2 CSV.",
            "Legacy V3 narrative claims were not automatically certified.",
            "Manager review rank is distinct from Python screening rank.",
            "Passing factual checks does not establish causation.",
        ],
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=== V3 TO V4 EVIDENCE BRIDGE ===")
    print("Target:", TARGET_DATE)
    print("Evidence ID:", evidence_id)
    print("Manager Review Rank:", target["rank"])
    print("Python Screening Rank:", row["screening_rank"])
    print("Claims Checked:", len(claims))
    print("Claims Passed:", sum(r["passed"] for r in results))
    print("All Passed:", all_passed)
    print("Legacy Narrative: HUMAN_REVIEW_REQUIRED")
    print("Saved:", output_path)

    if not all_passed:
        raise RuntimeError("Evidence validation failed")


if __name__ == "__main__":
    main()

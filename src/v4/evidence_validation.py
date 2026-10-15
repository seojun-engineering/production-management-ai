"""V4 evidence validation (offline, stdlib only).

Structured V4 claims are checked against committed V2 CSV records.
Legacy V3 natural-language evidence is NOT automatically certified.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ABS_TOL = 1e-6
REL_TOL = 1e-6

# Explicit metric semantics; different definitions must never be mixed.
METRICS = {
    "production_units": ("units", "daily"),
    "operating_ratio": ("ratio", "daily"),
    "downtime_h": ("hourly_record_hours", "daily"),
    "event_count": ("events", "daily"),
    "screening_score": ("relative_score", "daily"),
    "screening_rank": ("rank", "daily"),
    "event_share_pct": ("percent_of_events", "duration_group"),
    "duration_share_pct": ("percent_of_event_log_duration", "duration_group"),
    "event_duration_minutes": ("event_log_minutes", "event"),
}


def rows(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def registry(root=ROOT):
    daily = rows(root / "results/v2_daily_kpi_screening.csv")
    groups = rows(root / "results/v2_downtime_duration_groups.csv")
    events = rows(root / "data/processed/v2_downtime_events.csv")
    indexed = {}
    for row in daily:
        key = "V2-DAILY-" + row["date"]
        if key in indexed:
            raise ValueError(f"duplicate evidence id: {key}")
        indexed[key] = {"kind": "daily", "row": row}
    for n, row in enumerate(groups, 1):
        indexed[f"V2-DURATION-GROUP-{n}"] = {"kind": "duration_group", "row": row}
    for row in events:
        key = "V2-EVENT-" + row["downtime_id"]
        if key in indexed:
            raise ValueError(f"duplicate evidence id: {key}")
        indexed[key] = {"kind": "event", "row": row}
    return indexed


def issue(code, field, evidence_id, detail):
    return {"code": code, "field": field, "evidence_id": evidence_id, "detail": detail}


def validate(claim, indexed):
    """Validate one structured, factual claim. Fails closed on unknown fields.

    Required: evidence_id, metric, value, unit, aggregation.
    Optional: date, product, selection_rule, interpretation, cause_status.
    """
    problems = []
    eid = claim.get("evidence_id")
    record = indexed.get(eid)
    if record is None:
        problems.append(issue("UNKNOWN_EVIDENCE_ID", "evidence_id", eid, "No matching registry record"))
        return {"passed": False, "review_required": False, "errors": problems, "evidence_id": eid}
    kind, row = record["kind"], record["row"]
    metric = claim.get("metric")
    if metric not in METRICS:
        problems.append(issue("UNKNOWN_METRIC", "metric", eid, str(metric)))
    else:
        expected_unit, expected_kind = METRICS[metric]
        if kind != expected_kind or claim.get("aggregation") != expected_kind:
            problems.append(issue("AGGREGATION_MISMATCH", "aggregation", eid, f"required {expected_kind}; registry kind {kind}"))
        if claim.get("unit") != expected_unit:
            problems.append(issue("UNIT_MISMATCH", "unit", eid, f"required {expected_unit}"))
        col = "downtime_minutes" if metric == "event_duration_minutes" else metric
        if col not in row:
            problems.append(issue("METRIC_NOT_IN_SOURCE", "metric", eid, col))
        else:
            try:
                actual = float(row[col]); asserted = float(claim["value"])
                if not (math.isfinite(actual) and math.isfinite(asserted) and math.isclose(actual, asserted, rel_tol=REL_TOL, abs_tol=ABS_TOL)):
                    problems.append(issue("VALUE_MISMATCH", "value", eid, f"source={actual}, claim={asserted}"))
            except (ValueError, TypeError, KeyError):
                problems.append(issue("INVALID_NUMBER", "value", eid, "Non-finite, missing or non-numeric"))
    if "date" in claim:
        if "date" not in row or claim["date"] != row["date"]:
            problems.append(
                issue(
                    "DATE_MISMATCH",
                    "date",
                    eid,
                    f"source={row.get('date')}"
                )
            )

    if "product" in claim:
        source_product = row.get(
            "product_mix_l",
            row.get("product_type_l")
        )
        if str(claim["product"]) != str(source_product):
            problems.append(
                issue(
                    "PRODUCT_MISMATCH",
                    "product",
                    eid,
                    f"source={source_product}"
                )
            )

    if "selection_rule" in claim:
        rule = claim["selection_rule"]

        if rule == "screening_top_5":
            rank = row.get("screening_rank")
            try:
                valid = (
                    math.isfinite(float(rank))
                    and 1 <= float(rank) <= 5
                )
            except (ValueError, TypeError):
                valid = False

            if not valid:
                problems.append(
                    issue(
                        "SELECTION_RULE_FAILED",
                        "selection_rule",
                        eid,
                        f"rank={rank}"
                    )
                )
        else:
            problems.append(
                issue(
                    "UNKNOWN_SELECTION_RULE",
                    "selection_rule",
                    eid,
                    str(rule)
                )
            )

    if claim.get("cause_status") not in (
        None,
        "NOT_ESTABLISHED"
    ):
        problems.append(
            issue(
                "UNVERIFIED_CAUSAL_CLAIM",
                "cause_status",
                eid,
                "Cause not established"
            )
        )

    if claim.get("effect_verified", False) is not False:
        problems.append(
            issue(
                "UNVERIFIED_EFFECT_CLAIM",
                "effect_verified",
                eid,
                "No verified intervention effect"
            )
        )

    review_required = bool(claim.get("interpretation"))

    return {
        "passed": not problems,
        "review_required": review_required and not problems,
        "errors": problems,
        "evidence_id": eid
    }

# ==================================================
# BATCH VALIDATION
# ==================================================

def validate_batch(claims, root=ROOT):
    indexed = registry(root)

    results = [
        validate(claim, indexed)
        for claim in claims
    ]

    passed = sum(
        result["passed"]
        for result in results
    )

    return {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results
    }


# ==================================================
# COMMAND LINE EXECUTION
# ==================================================

def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="V4 Evidence Validation"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Input JSON containing evidence claims"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON for validation results"
    )

    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, list):
        claims = payload
    elif isinstance(payload, dict) and isinstance(
        payload.get("claims"), list
    ):
        claims = payload["claims"]
    else:
        raise ValueError(
            "Input must be a list or an object containing a claims list."
        )

    results = validate_batch(claims)

    output_path = Path(args.output)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(
            results,
            f,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"Claims: {results['total']} | "
        f"PASS: {results['passed']} | "
        f"FAIL: {results['failed']}"
    )

    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
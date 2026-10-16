
from pathlib import Path
import json
from evidence_validation import registry, validate

ROOT = Path(__file__).resolve().parents[2]

INPUT = ROOT / "results/v4/v3_bridge_demo.json"
OUTPUT = ROOT / "results/v4/next_check_demo.json"


def generate_next_checks(bridge):
    results = bridge.get("validation_results", [])

    # 검증을 통과하지 않은 근거는 사용하지 않음
    if (
        not bridge.get("all_factual_claims_passed")
        or len(results) != 5
        or not all(r.get("passed") for r in results)
    ):
        raise ValueError("Evidence validation failed.")

    claims = {
        item["metric"]: item
        for item in bridge["factual_claims"]
    }

    required_metrics = {
        "screening_rank",
        "screening_score",
        "operating_ratio",
        "downtime_h",
        "event_count",
    }

    if set(claims) != required_metrics:
        raise ValueError("Unexpected evidence metrics.")

    evidence_id = bridge["evidence_id"]
    target_date = bridge["target_date"]

    # ID와 날짜가 서로 일치하는지 확인
    expected_id = f"V2-DAILY-{target_date}"

    if evidence_id != expected_id:
        raise ValueError("Evidence ID and date mismatch.")

    if any(
        claim["evidence_id"] != evidence_id
        for claim in claims.values()
    ):
        raise ValueError("Inconsistent Evidence IDs.")

    # Revalidate every claim against the V2 Evidence Registry.
    # Do not trust a previously saved validation flag alone.

    indexed = registry(ROOT)

    if evidence_id not in indexed:
        raise ValueError(
            f"Evidence ID not found in source: {evidence_id}"
        )

    for claim in claims.values():
        validation = validate(claim, indexed)

        if not validation["passed"]:
            error_codes = [
                error["code"]
                for error in validation["errors"]
            ]

            raise ValueError(
                f"Evidence revalidation failed "
                f"for {claim['metric']}: {error_codes}"
            )

    rank = float(claims["screening_rank"]["value"])

    if not 1 <= rank <= 5:
        raise ValueError(
            "Target does not satisfy screening_top_5."
        )

    # Python 규칙 기반 점검 후보 생성
    checks = [
        {
            "check_id": "CHECK-001",
            "category": "production_record",
            "question": (
                "해당 날짜의 생산계획과 실제 생산량은 "
                "일치했는가?"
            ),
            "required_data": [
                "planned_production_qty",
                "actual_production_qty",
                "production_schedule",
            ],
            "if_confirmed": (
                "생산계획 달성 여부와 부족 수량을 확인한다."
            ),
            "if_not_confirmed": (
                "생산계획과 실적의 집계 기준을 재검증한다."
            ),
        },
        {
            "check_id": "CHECK-002",
            "category": "downtime_reconciliation",
            "question": (
                "시간별 비운영시간과 이벤트 로그의 "
                "기록 범위가 일치하는가?"
            ),
            "required_data": [
                "hourly_operation_record",
                "downtime_event_log",
                "event_timestamp",
            ],
            "if_confirmed": (
                "시간별 비운영시간 분포와 이벤트 발생 패턴을 검토한다."
            ),
            "if_not_confirmed": (
                "기록 누락과 시간 정의 차이를 점검한다."
            ),
        },
        {
            "check_id": "CHECK-003",
            "category": "downtime_reason",
            "question": (
                "비운영시간이 계획정지, 세척, 품목교체, "
                "고장 등 어떤 사유와 관련되는가?"
            ),
            "required_data": [
                "downtime_reason_code",
                "equipment_id",
                "maintenance_record",
                "operator_comment",
            ],
            "if_confirmed": (
                "확인된 사유를 관련 원천 기록과 대조한다."
            ),
            "if_not_confirmed": (
                "원인을 미확정 상태로 유지하고 "
                "추가 기록을 요청한다."
            ),
        },
    ]

    return {
        "review_id": bridge["review_id"],
        "target_date": target_date,
        "target_type": bridge["target_type"],
        "evidence_ids": [evidence_id],
        "observations": [
            {
                "metric": metric,
                "value": claims[metric]["value"],
                "unit": claims[metric]["unit"],
            }
            for metric in sorted(required_metrics)
        ],
        "selection_reason": (
            f"Python Screening Rank {int(rank)} "
            "(relative screening_top_5)"
        ),
        "selection_rule": "screening_top_5",
        "checks": checks,
        "root_cause_status": "NOT_ESTABLISHED",
        "action_status": "NOT_REVIEWED",
        "data_type": "REAL_OBSERVATION",
        "interpretation_status": "HUMAN_REVIEW_REQUIRED",
    }


def main():
    bridge = json.loads(
        INPUT.read_text(encoding="utf-8")
    )

    result = generate_next_checks(bridge)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=== V4 NEXT CHECK ENGINE ===")
    print("Review ID:", result["review_id"])
    print("Target:", result["target_date"])
    print("Evidence:", result["evidence_ids"][0])
    print("Checks Generated:", len(result["checks"]))
    print("Root Cause:", result["root_cause_status"])
    print("Saved:", OUTPUT)


if __name__ == "__main__":
    main()

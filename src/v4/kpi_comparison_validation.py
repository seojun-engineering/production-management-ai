
from datetime import datetime
from math import isfinite
from action_evidence_validation import validate_action_evidence

MIN_SAMPLES = 5


def validate_comparison(data, action_validator=validate_action_evidence):
    """
    Check whether a before/after KPI comparison is justified.
    No improvement rate is calculated here.
    """

    # 실제 Action Evidence를 확인하기 전에는 KPI 비교를 허용하지 않음
    action_id = data.get("action_id")

    if not action_id:
        action_evidence = {
            "verified": False,
            "reason": "MISSING_ACTION_ID",
        }
    else:
        action_evidence = action_validator(action_id)

    errors = []

    def reject(code, detail):
        errors.append({
            "code": code,
            "detail": detail,
        })

    if action_evidence.get("verified") is not True:
        reject(
            "ACTION_EVIDENCE_NOT_VERIFIED",
            action_evidence.get("reason", "UNKNOWN_REASON")
        )

    # 1. 실제 조치 여부
    if data.get("record_origin") != "REAL_ACTION":
        reject(
            "NOT_REAL_ACTION",
            "Demo or unverified actions cannot establish improvement."
        )

    if data.get("action_status") != "COMPLETED":
        reject(
            "ACTION_NOT_COMPLETED",
            "The action must be completed."
        )

    # 2. 조치 시각 검증
    action_time = None

    try:
        action_time = datetime.fromisoformat(
            data["action_timestamp"]
        )
        if action_time.tzinfo is None:
            raise ValueError("Timezone required")
    except (KeyError, TypeError, ValueError):
        reject(
            "INVALID_ACTION_TIMESTAMP",
            "A valid timezone-aware action timestamp is required."
        )

    before = data.get("before", {})
    after = data.get("after", {})

    if not isinstance(before, dict):
        before = {}
    if not isinstance(after, dict):
        after = {}

    # 3. KPI 정의와 집계 조건
    for field in (
        "metric",
        "unit",
        "denominator",
        "aggregation",
        "product",
        "process",
    ):
        if (
            not before.get(field)
            or not after.get(field)
            or before[field] != after[field]
        ):
            reject(
                "COMPARISON_SCOPE_MISMATCH",
                f"Missing or inconsistent field: {field}"
            )

    # 4. 표본 수 검증
    for label, period in (("before", before), ("after", after)):
        count = period.get("sample_count")

        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or count < MIN_SAMPLES
        ):
            reject(
                "INSUFFICIENT_SAMPLES",
                f"{label}: at least {MIN_SAMPLES} samples required."
            )

        # 기록 누락 여부
        if period.get("data_complete") is not True:
            reject(
                "INCOMPLETE_DATA",
                f"{label}: data completeness not established."
            )

        value = period.get("value")

        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
        ):
            reject(
                "INVALID_KPI_VALUE",
                f"{label}: valid numeric KPI required."
            )

   
    # 5. 비교 기간 전체와 조치 시점 검증
    try:
        before_start = datetime.fromisoformat(before["start"])
        before_end = datetime.fromisoformat(before["end"])
        after_start = datetime.fromisoformat(after["start"])
        after_end = datetime.fromisoformat(after["end"])

        boundaries = [
            before_start,
            before_end,
            after_start,
            after_end,
        ]

        if any(dt.tzinfo is None or dt.utcoffset() is None
               for dt in boundaries):
            raise ValueError("Timezone required")

        if before_start >= before_end:
            reject(
                "INVALID_BEFORE_PERIOD",
                "Before start must precede before end."
            )

        if after_start >= after_end:
            reject(
                "INVALID_AFTER_PERIOD",
                "After start must precede after end."
            )

        if before_end >= after_start:
            reject(
                "PERIOD_OVERLAP",
                "Before and after periods must not overlap."
            )

        if action_time is not None:
            if not before_end < action_time < after_start:
                reject(
                    "ACTION_OUTSIDE_GAP",
                    "Action must occur between the comparison periods."
                )

    except (KeyError, TypeError, ValueError):
        reject(
            "INVALID_COMPARISON_PERIOD",
            "Valid timezone-aware period boundaries required."
        )

    return {
        "status": (
            "COMPARABLE"
            if not errors
            else "NOT_COMPARABLE"
        ),
        "can_calculate_improvement": len(errors) == 0,
        "errors": errors,
        "improvement_rate": None,
        "root_cause_status": "NOT_ESTABLISHED",
    }

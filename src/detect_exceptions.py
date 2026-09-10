from pathlib import Path
import sys
import pandas as pd

# src 폴더 안의 calculate_kpi.py 불러오기
sys.path.append(str(Path(__file__).resolve().parent))

from calculate_kpi import calculate_kpi


THRESHOLDS = {
    "schedule_attainment": 0.95,
    "defect_rate": 0.03,
    "equipment_utilization": 0.85,
}


def detect_exceptions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect production KPI exceptions using fixed management rules.
    """

    result = df.copy()

    result["schedule_exception"] = (
        result["schedule_attainment"] < THRESHOLDS["schedule_attainment"]
    )

    result["defect_exception"] = (
        result["defect_rate"] > THRESHOLDS["defect_rate"]
    )

    result["utilization_exception"] = (
        result["equipment_utilization"] < THRESHOLDS["equipment_utilization"]
    )

    result["is_exception"] = (
        result[
            [
                "schedule_exception",
                "defect_exception",
                "utilization_exception",
            ]
        ].any(axis=1)
    )

    return result


def build_exception_reason(row):
    reasons = []

    if row["schedule_exception"]:
        reasons.append("Low Schedule Attainment")

    if row["defect_exception"]:
        reasons.append("High Defect Rate")

    if row["utilization_exception"]:
        reasons.append("Low Equipment Utilization")

    return " | ".join(reasons)


def main():
    base_dir = Path(__file__).resolve().parent.parent
    input_path = base_dir / "data" / "sample_production_data.csv"

    raw_df = pd.read_csv(input_path)

    kpi_df = calculate_kpi(raw_df)

    result = detect_exceptions(kpi_df)

    result["exception_reason"] = result.apply(
        build_exception_reason,
        axis=1
    )

    exceptions = result[result["is_exception"]].copy()

    columns = [
        "date",
        "product_code",
        "schedule_attainment",
        "defect_rate",
        "equipment_utilization",
        "exception_reason",
    ]

    print("\n=== Production Exceptions ===\n")
    print(exceptions[columns].round(4).to_string(index=False))

    print(f"\nTotal records: {len(result)}")
    print(f"Exception records: {len(exceptions)}")


if __name__ == "__main__":
    main()

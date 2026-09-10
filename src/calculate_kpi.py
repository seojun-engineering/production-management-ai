from pathlib import Path
import pandas as pd


def calculate_kpi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate production management KPIs.

    KPIs
    ----
    schedule_attainment:
        actual_qty / planned_qty

    defect_rate:
        defect_qty / actual_qty

    equipment_utilization:
        operating_time_hr / available_time_hr
    """

    result = df.copy()

    result["schedule_attainment"] = (
        result["actual_qty"] / result["planned_qty"]
    )

    result["defect_rate"] = (
        result["defect_qty"] / result["actual_qty"]
    )

    result["equipment_utilization"] = (
        result["operating_time_hr"] / result["available_time_hr"]
    )

    return result


def main():
    base_dir = Path(__file__).resolve().parent.parent
    input_path = base_dir / "data" / "sample_production_data.csv"

    df = pd.read_csv(input_path)

    result = calculate_kpi(df)

    print(
        result[
            [
                "date",
                "product_code",
                "schedule_attainment",
                "defect_rate",
                "equipment_utilization",
            ]
        ].round(4)
    )


if __name__ == "__main__":
    main()

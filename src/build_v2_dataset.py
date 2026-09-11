from pathlib import Path
import pandas as pd
import numpy as np


def normalize_dates(df):
    df = df.copy()
    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    ).dt.normalize()

    return df


def main():
    base_dir = Path(__file__).resolve().parent.parent

    raw_path = (
        base_dir
        / "data"
        / "real"
        / "production_raw.xlsx"
    )

    output_dir = (
        base_dir
        / "data"
        / "processed"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    sheets = pd.read_excel(
        raw_path,
        sheet_name=None
    )

    daily = normalize_dates(
        sheets["daily_operation_summary"]
    )

    hourly = normalize_dates(
        sheets["hourly_operation_breakdown"]
    )

    downtime = normalize_dates(
        sheets["downtime_event_log"]
    )

    # ==================================================
    # 1. DOWNTIME DATE CORRECTION
    # ==================================================

    wrong_date = pd.Timestamp("2022-01-13")
    corrected_date = pd.Timestamp("2023-01-13")

    correction_mask = (
        downtime["date"] == wrong_date
    )

    corrected_rows = correction_mask.sum()

    downtime["date_corrected"] = False

    downtime.loc[
        correction_mask,
        "date"
    ] = corrected_date

    downtime.loc[
        correction_mask,
        "date_corrected"
    ] = True

    # ==================================================
    # 2. CANONICAL DAILY DATA
    # ==================================================

    daily["operating_ratio"] = (
        daily["operation_time_dec"]
        / daily["monitored_time_dec"]
    )

    daily["derived_nonoperation_h"] = (
        daily["monitored_time_dec"]
        - daily["operation_time_dec"]
    )

    daily["pause_difference_h"] = (
        daily["pause_time_dec"]
        - daily["derived_nonoperation_h"]
    )

    daily["pause_definition_mismatch"] = (
        daily["pause_difference_h"]
        .abs()
        > 0.01
    )

    daily["expected_liters"] = (
        daily["product_type_l"]
        * daily["production_units"]
    )

    daily["liter_validation_error"] = (
        daily["liters_produced"]
        - daily["expected_liters"]
    )

    rows_per_date = (
        daily.groupby("date")["date"]
        .transform("size")
    )

    daily["multi_product_day"] = (
        rows_per_date > 1
    )

    daily = daily.rename(
        columns={
            "efficiency":
                "source_efficiency",

            "gallons_per_hour":
                "source_gallons_per_hour",

            "pause_time_dec":
                "source_pause_time_h",
        }
    )

    # ==================================================
    # 3. CANONICAL HOURLY OPERATION DATA
    # ==================================================

    hourly["calculated_monitored_h"] = (
        hourly["operation_time_h"]
        + hourly["downtime_h"]
    )

    hourly["monitored_validation_error"] = (
        hourly["monitored_time_h"]
        - hourly["calculated_monitored_h"]
    )

    hourly["operating_ratio"] = np.where(
        hourly["monitored_time_h"] > 0,
        hourly["operation_time_h"]
        / hourly["monitored_time_h"],
        0
    )

    hourly["efficiency_validation_error"] = (
        hourly["efficiency"]
        - hourly["operating_ratio"]
    )

    hourly = hourly.rename(
        columns={
            "efficiency":
                "source_efficiency"
        }
    )

    # ==================================================
    # 4. CANONICAL DOWNTIME EVENTS
    # ==================================================

    downtime["downtime_duration"] = (
        pd.to_timedelta(
            downtime["downtime_time"]
            .astype(str),
            errors="coerce"
        )
    )

    downtime["downtime_seconds"] = (
        downtime[
            "downtime_duration"
        ]
        .dt.total_seconds()
    )

    downtime["downtime_minutes"] = (
        downtime["downtime_seconds"]
        / 60
    )

    downtime["downtime_hours"] = (
        downtime["downtime_seconds"]
        / 3600
    )

    downtime["event_count"] = 1

    # ==================================================
    # 5. SAVE CANONICAL DATASETS
    # ==================================================

    daily_path = (
        output_dir
        / "v2_daily_production.csv"
    )

    hourly_path = (
        output_dir
        / "v2_hourly_operation.csv"
    )

    downtime_path = (
        output_dir
        / "v2_downtime_events.csv"
    )

    daily.to_csv(
        daily_path,
        index=False
    )

    hourly.to_csv(
        hourly_path,
        index=False
    )

    downtime.to_csv(
        downtime_path,
        index=False
    )

    # ==================================================
    # 6. QUALITY SUMMARY
    # ==================================================

    print(
        "\n=== V2 CANONICAL DATA BUILD ==="
    )

    print(
        f"\nCorrected downtime date rows: "
        f"{corrected_rows}"
    )

    print(
        "\nDaily production rows:",
        len(daily)
    )

    print(
        "Hourly operation rows:",
        len(hourly)
    )

    print(
        "Downtime event rows:",
        len(downtime)
    )

    print(
        "\nMulti-product daily rows:",
        daily[
            "multi_product_day"
        ].sum()
    )

    print(
        "Pause-definition mismatch rows:",
        daily[
            "pause_definition_mismatch"
        ].sum()
    )

    print(
        "\nDowntime date range:",
        downtime["date"].min(),
        "→",
        downtime["date"].max()
    )

    print(
        "\nFiles created:"
    )

    print(daily_path)
    print(hourly_path)
    print(downtime_path)


if __name__ == "__main__":
    main()
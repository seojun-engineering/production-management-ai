from pathlib import Path
import pandas as pd


def inspect_sheet(name, df):
    print("\n" + "=" * 70)
    print(f"SHEET: {name}")
    print("=" * 70)

    print(f"Rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")

    print("\n--- Data Types ---")
    print(df.dtypes)

    print("\n--- Missing Values ---")
    print(df.isna().sum())

    print("\n--- Duplicate Rows ---")
    print(df.duplicated().sum())

    print("\n--- First 5 Rows ---")
    print(df.head().to_string(index=False))


def main():
    base_dir = Path(__file__).resolve().parent.parent
    path = base_dir / "data" / "real" / "production_raw.xlsx"

    sheets = pd.read_excel(
        path,
        sheet_name=None
    )

    for name, df in sheets.items():
        inspect_sheet(name, df)

    # --------------------------------------------------
    # Date coverage
    # --------------------------------------------------

    print("\n" + "=" * 70)
    print("DATE COVERAGE")
    print("=" * 70)

    for name, df in sheets.items():
        if "date" in df.columns:
            dates = pd.to_datetime(df["date"], errors="coerce")

            print(
                f"{name}: "
                f"{dates.min()} → {dates.max()} "
                f"| unique dates = {dates.nunique()}"
            )

    # --------------------------------------------------
    # Daily production structure
    # --------------------------------------------------

    daily = sheets["daily_operation_summary"].copy()
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce")

    rows_per_date = (
        daily.groupby("date")
        .size()
        .sort_values(ascending=False)
    )

    print("\n" + "=" * 70)
    print("DAILY SUMMARY STRUCTURE")
    print("=" * 70)

    print("\nRows per production date:")
    print(rows_per_date.value_counts().sort_index())

    multi_row_dates = rows_per_date[rows_per_date > 1]

    print(
        "\nDates containing more than one daily-summary row:",
        len(multi_row_dates)
    )

    if len(multi_row_dates) > 0:
        print("\nExamples:")
        print(
            daily[
                daily["date"].isin(
                    multi_row_dates.index[:10]
                )
            ][
                [
                    "date",
                    "product_type_l",
                    "production_units",
                    "efficiency",
                    "gallons_per_hour",
                ]
            ].to_string(index=False)
        )

    print("\nUnique product types:")
    print(
        daily["product_type_l"]
        .value_counts(dropna=False)
    )

    # --------------------------------------------------
    # KPI distributions
    # --------------------------------------------------

    print("\n" + "=" * 70)
    print("DAILY KPI DISTRIBUTIONS")
    print("=" * 70)

    kpi_columns = [
        "production_units",
        "liters_produced",
        "efficiency",
        "gallons_per_hour",
        "monitored_time_dec",
        "operation_time_dec",
        "pause_time_dec",
    ]

    print(
        daily[kpi_columns]
        .describe()
        .round(3)
        .to_string()
    )

    # --------------------------------------------------
    # Hourly operation data
    # --------------------------------------------------

    hourly = sheets["hourly_operation_breakdown"].copy()
    hourly["date"] = pd.to_datetime(
        hourly["date"],
        errors="coerce"
    )

    print("\n" + "=" * 70)
    print("HOURLY OPERATION DISTRIBUTIONS")
    print("=" * 70)

    hourly_columns = [
        "monitored_time_h",
        "operation_time_h",
        "downtime_h",
        "efficiency",
    ]

    print(
        hourly[hourly_columns]
        .describe()
        .round(3)
        .to_string()
    )

    # --------------------------------------------------
    # Downtime event structure
    # --------------------------------------------------

    downtime = sheets["downtime_event_log"].copy()
    downtime["date"] = pd.to_datetime(
        downtime["date"],
        errors="coerce"
    )

    print("\n" + "=" * 70)
    print("DOWNTIME EVENT STRUCTURE")
    print("=" * 70)

    print("\nDowntime_time dtype:")
    print(downtime["downtime_time"].dtype)

    print("\nExample downtime_time values:")
    print(
        downtime["downtime_time"]
        .head(10)
        .to_string(index=False)
    )

    events_per_day = (
        downtime.groupby("date")
        .size()
        .sort_values(ascending=False)
    )

    print("\nDowntime events per day:")
    print(events_per_day.describe().round(2))

    print("\nTop 10 dates by number of downtime events:")
    print(events_per_day.head(10))


if __name__ == "__main__":
    main()
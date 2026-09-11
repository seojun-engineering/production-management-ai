from pathlib import Path
import pandas as pd
import numpy as np


def main():
    base_dir = Path(__file__).resolve().parent.parent
    path = base_dir / "data" / "real" / "production_raw.xlsx"

    sheets = pd.read_excel(path, sheet_name=None)

    processed = sheets["processed_hourly"].copy()
    daily = sheets["daily_operation_summary"].copy()
    hourly = sheets["hourly_operation_breakdown"].copy()
    downtime = sheets["downtime_event_log"].copy()

    # --------------------------------------------------
    # Normalize dates
    # --------------------------------------------------

    for df in [processed, daily, hourly, downtime]:
        df["date"] = pd.to_datetime(
            df["date"],
            errors="coerce"
        ).dt.normalize()

    # ==================================================
    # 1. DATE SET CHECK
    # ==================================================

    print("\n" + "=" * 70)
    print("DATE SET CHECK")
    print("=" * 70)

    daily_dates = set(daily["date"].dropna())
    processed_dates = set(processed["date"].dropna())
    hourly_dates = set(hourly["date"].dropna())
    downtime_dates = set(downtime["date"].dropna())

    print("\nDaily dates missing from processed_hourly:")
    print(sorted(daily_dates - processed_dates))

    print("\nDaily dates missing from hourly_operation_breakdown:")
    print(sorted(daily_dates - hourly_dates))

    print("\nDaily dates missing from downtime_event_log:")
    print(sorted(daily_dates - downtime_dates))

    print("\nDowntime dates not present in daily summary:")
    print(sorted(downtime_dates - daily_dates))

    daily_min = daily["date"].min()
    daily_max = daily["date"].max()

    suspicious_downtime = downtime[
        (downtime["date"] < daily_min)
        | (downtime["date"] > daily_max)
    ]

    print("\nSuspicious downtime records outside daily date range:")
    print(
        suspicious_downtime.head(20).to_string(index=False)
        if len(suspicious_downtime)
        else "None"
    )

    # ==================================================
    # 2. DAILY FORMULA VALIDATION
    # ==================================================

    print("\n" + "=" * 70)
    print("DAILY FORMULA VALIDATION")
    print("=" * 70)

    daily["expected_liters"] = (
        daily["product_type_l"]
        * daily["production_units"]
    )

    daily["calc_efficiency"] = (
        daily["operation_time_dec"]
        / daily["monitored_time_dec"]
    )

    daily["calc_pause"] = (
        daily["monitored_time_dec"]
        - daily["operation_time_dec"]
    )

    daily["calc_units_per_operation_hour"] = (
        daily["production_units"]
        / daily["operation_time_dec"]
    )

    print(
        "\nLiters produced = product size × production units"
    )
    print(
        "Max absolute error:",
        (
            daily["liters_produced"]
            - daily["expected_liters"]
        ).abs().max()
    )

    print(
        "\nEfficiency = operation time / monitored time"
    )
    print(
        "Max absolute error:",
        (
            daily["efficiency"]
            - daily["calc_efficiency"]
        ).abs().max()
    )

    print(
        "\nPause time = monitored time - operation time"
    )
    print(
        "Max absolute error:",
        (
            daily["pause_time_dec"]
            - daily["calc_pause"]
        ).abs().max()
    )

    print(
        "\n'gallons_per_hour' vs production_units / operation_time"
    )
    print(
        "Max absolute error:",
        (
            daily["gallons_per_hour"]
            - daily["calc_units_per_operation_hour"]
        ).abs().max()
    )

    # ==================================================
    # 3. HOURLY FORMULA VALIDATION
    # ==================================================

    print("\n" + "=" * 70)
    print("HOURLY FORMULA VALIDATION")
    print("=" * 70)

    hourly["calc_monitored"] = (
        hourly["operation_time_h"]
        + hourly["downtime_h"]
    )

    hourly["calc_efficiency"] = np.where(
        hourly["monitored_time_h"] > 0,
        hourly["operation_time_h"]
        / hourly["monitored_time_h"],
        0
    )

    print(
        "\nMonitored = operation + downtime"
    )
    print(
        "Max absolute error:",
        (
            hourly["monitored_time_h"]
            - hourly["calc_monitored"]
        ).abs().max()
    )

    print(
        "\nHourly efficiency = operation / monitored"
    )
    print(
        "Max absolute error:",
        (
            hourly["efficiency"]
            - hourly["calc_efficiency"]
        ).abs().max()
    )

    # ==================================================
    # 4. DAILY PRODUCTION RECONCILIATION
    # ==================================================

    print("\n" + "=" * 70)
    print("DAILY PRODUCTION RECONCILIATION")
    print("=" * 70)

    processed_daily = (
        processed.groupby("date")["production_gallons"]
        .sum()
        .rename("processed_sum")
    )

    daily_units = (
        daily.groupby("date")["production_units"]
        .sum()
        .rename("daily_units")
    )

    production_compare = pd.concat(
        [processed_daily, daily_units],
        axis=1
    )

    production_compare["difference"] = (
        production_compare["processed_sum"]
        - production_compare["daily_units"]
    )

    print("\nComparison of processed_hourly sum vs daily production units:")
    print(
        production_compare.head(15).to_string()
    )

    print(
        "\nMax absolute difference:",
        production_compare["difference"].abs().max()
    )

    print(
        "\nDates with mismatch:"
    )
    print(
        production_compare[
            production_compare["difference"].abs() > 0.001
        ].to_string()
    )

    # ==================================================
    # 5. DOWNTIME RECONCILIATION
    # ==================================================

    print("\n" + "=" * 70)
    print("DOWNTIME RECONCILIATION")
    print("=" * 70)

    downtime["downtime_td"] = pd.to_timedelta(
        downtime["downtime_time"].astype(str),
        errors="coerce"
    )

    downtime["downtime_hours"] = (
        downtime["downtime_td"]
        .dt.total_seconds()
        / 3600
    )

    event_daily = (
        downtime.groupby("date")["downtime_hours"]
        .sum()
        .rename("event_downtime_h")
    )

    hourly_daily = (
        hourly.groupby("date")["downtime_h"]
        .sum()
        .rename("hourly_downtime_h")
    )

    daily_pause = (
        daily.groupby("date")["pause_time_dec"]
        .sum()
        .rename("daily_pause_h")
    )

    downtime_compare = pd.concat(
        [
            event_daily,
            hourly_daily,
            daily_pause
        ],
        axis=1
    )

    downtime_compare["event_vs_hourly"] = (
        downtime_compare["event_downtime_h"]
        - downtime_compare["hourly_downtime_h"]
    )

    downtime_compare["event_vs_daily"] = (
        downtime_compare["event_downtime_h"]
        - downtime_compare["daily_pause_h"]
    )

    print("\nFirst 15 dates:")
    print(
        downtime_compare.head(15).round(4).to_string()
    )

    print(
        "\nLargest Event vs Hourly differences:"
    )
    print(
        downtime_compare[
            ["event_vs_hourly"]
        ]
        .abs()
        .sort_values(
            "event_vs_hourly",
            ascending=False
        )
        .head(10)
        .to_string()
    )


if __name__ == "__main__":
    main()
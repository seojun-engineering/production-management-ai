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

    for df in [processed, daily, hourly, downtime]:
        df["date"] = pd.to_datetime(
            df["date"], errors="coerce"
        ).dt.normalize()

    # ==================================================
    # 1. SUSPICIOUS JANUARY DATE
    # ==================================================

    print("\n" + "=" * 70)
    print("JANUARY DATE INVESTIGATION")
    print("=" * 70)

    for target in ["2022-01-13", "2023-01-13"]:
        target = pd.Timestamp(target)

        print(f"\n--- {target.date()} ---")

        print(
            "processed_hourly:",
            len(processed[processed["date"] == target])
        )

        print(
            "daily_summary:",
            len(daily[daily["date"] == target])
        )

        print(
            "hourly_breakdown:",
            len(hourly[hourly["date"] == target])
        )

        print(
            "downtime_events:",
            len(downtime[downtime["date"] == target])
        )

        if len(daily[daily["date"] == target]):
            print("\nDaily row:")
            print(
                daily[
                    daily["date"] == target
                ].to_string(index=False)
            )

    downtime["id_num"] = (
        downtime["downtime_id"]
        .str.extract(r"(\d+)", expand=False)
        .astype(int)
    )

    print("\nDowntime IDs around suspicious records:")
    print(
        downtime[
            downtime["id_num"].between(1238, 1275)
        ][
            [
                "downtime_id",
                "date",
                "downtime_start_time",
                "downtime_end_time",
                "downtime_time",
            ]
        ].to_string(index=False)
    )

    # ==================================================
    # 2. PAUSE FORMULA MISMATCH
    # ==================================================

    print("\n" + "=" * 70)
    print("PAUSE TIME MISMATCH")
    print("=" * 70)

    daily["calc_pause"] = (
        daily["monitored_time_dec"]
        - daily["operation_time_dec"]
    )

    daily["pause_difference"] = (
        daily["pause_time_dec"]
        - daily["calc_pause"]
    )

    pause_problem = daily[
        daily["pause_difference"].abs() > 1e-6
    ].copy()

    pause_problem["abs_difference"] = (
        pause_problem["pause_difference"].abs()
    )

    print(
        pause_problem[
            [
                "date",
                "product_type_l",
                "monitored_time_dec",
                "operation_time_dec",
                "pause_time_dec",
                "calc_pause",
                "pause_difference",
            ]
        ]
        .sort_values(
            "pause_difference",
            key=lambda s: s.abs(),
            ascending=False,
        )
        .to_string(index=False)
    )

    # ==================================================
    # 3. RATE COLUMN INVESTIGATION
    # ==================================================

    print("\n" + "=" * 70)
    print("RATE COLUMN INVESTIGATION")
    print("=" * 70)

    daily["calc_units_per_operation_hour"] = (
        daily["production_units"]
        / daily["operation_time_dec"]
    )

    daily["rate_difference"] = (
        daily["gallons_per_hour"]
        - daily["calc_units_per_operation_hour"]
    )

    rate_problem = daily[
        daily["rate_difference"].abs() > 1e-6
    ].copy()

    print(
        rate_problem[
            [
                "date",
                "product_type_l",
                "production_units",
                "operation_time_dec",
                "gallons_per_hour",
                "calc_units_per_operation_hour",
                "rate_difference",
            ]
        ]
        .sort_values(
            "rate_difference",
            key=lambda s: s.abs(),
            ascending=False,
        )
        .to_string(index=False)
    )

    print(
        "\nRows matching production_units / operation_time:",
        len(daily) - len(rate_problem),
        "/",
        len(daily),
    )

    # ==================================================
    # 4. HOURLY PRODUCTION VS DAILY PRODUCTION
    # ==================================================

    print("\n" + "=" * 70)
    print("PRODUCTION MISMATCH INVESTIGATION")
    print("=" * 70)

    processed_daily = (
        processed.groupby("date")["production_gallons"]
        .sum()
        .rename("hourly_sum")
    )

    daily_units = (
        daily.groupby("date")["production_units"]
        .sum()
        .rename("daily_units")
    )

    compare = pd.concat(
        [processed_daily, daily_units],
        axis=1,
        sort=False,
    )

    compare["difference"] = (
        compare["hourly_sum"]
        - compare["daily_units"]
    )

    mismatch_dates = compare[
        compare["difference"].abs() > 1e-6
    ]

    print(mismatch_dates.to_string())

    for date in mismatch_dates.index:
        print(f"\n--- {date.date()} ---")

        print("\nDaily rows:")
        print(
            daily[
                daily["date"] == date
            ][
                [
                    "date",
                    "product_type_l",
                    "production_units",
                    "production_start_time",
                    "production_end_time",
                ]
            ].to_string(index=False)
        )

        print("\nHourly production:")
        print(
            processed[
                processed["date"] == date
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()
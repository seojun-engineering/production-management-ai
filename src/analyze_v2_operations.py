from pathlib import Path
import pandas as pd
import numpy as np


def iqr_limits(series):
    """
    Calculate Tukey IQR lower/upper outlier limits.
    """
    series = series.dropna()

    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1

    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    return q1, q3, lower, upper


def main():
    base_dir = Path(__file__).resolve().parent.parent

    processed_dir = base_dir / "data" / "processed"
    results_dir = base_dir / "results"
    results_dir.mkdir(exist_ok=True)

    # ==================================================
    # 1. LOAD CANONICAL V2 DATA
    # ==================================================

    daily = pd.read_csv(
        processed_dir / "v2_daily_production.csv"
    )

    hourly = pd.read_csv(
        processed_dir / "v2_hourly_operation.csv"
    )

    events = pd.read_csv(
        processed_dir / "v2_downtime_events.csv"
    )

    for df in [daily, hourly, events]:
        df["date"] = pd.to_datetime(df["date"])

    # ==================================================
    # 2. DAILY OPERATION KPI FROM HOURLY DATA
    # ==================================================

    hourly_daily = (
        hourly
        .groupby("date")
        .agg(
            monitored_time_h=(
                "monitored_time_h",
                "sum"
            ),
            operation_time_h=(
                "operation_time_h",
                "sum"
            ),
            downtime_h=(
                "downtime_h",
                "sum"
            ),
            hourly_records=(
                "hour_start",
                "count"
            ),
        )
        .reset_index()
    )

    hourly_daily["operating_ratio"] = np.where(
        hourly_daily["monitored_time_h"] > 0,
        hourly_daily["operation_time_h"]
        / hourly_daily["monitored_time_h"],
        np.nan
    )

    # ==================================================
    # 3. DOWNTIME EVENT STATISTICS
    # ==================================================

    event_daily = (
        events
        .groupby("date")
        .agg(
            event_count=(
                "downtime_id",
                "count"
            ),
            median_event_minutes=(
                "downtime_minutes",
                "median"
            ),
            max_event_minutes=(
                "downtime_minutes",
                "max"
            ),
            event_duration_sum_minutes=(
                "downtime_minutes",
                "sum"
            ),
        )
        .reset_index()
    )

    # NOTE:
    # event_duration_sum_minutes is diagnostic only.
    # It is NOT treated as canonical downtime because
    # event-log duration did not reconcile consistently
    # with hourly downtime.

    # ==================================================
    # 4. DAILY PRODUCTION SUMMARY
    # ==================================================

    daily_date = (
        daily
        .groupby("date")
        .agg(
            production_units=(
                "production_units",
                "sum"
            ),
            liters_produced=(
                "liters_produced",
                "sum"
            ),
            product_count=(
                "product_type_l",
                "nunique"
            ),
        )
        .reset_index()
    )

    product_mix = (
        daily
        .groupby("date")["product_type_l"]
        .apply(
            lambda x: "|".join(
                sorted(
                    x.astype(str).unique()
                )
            )
        )
        .reset_index(
            name="product_mix_l"
        )
    )

    daily_date = daily_date.merge(
        product_mix,
        on="date",
        how="left"
    )

    # ==================================================
    # 5. MERGE DAILY EVIDENCE
    # ==================================================

    analysis = (
        daily_date
        .merge(
            hourly_daily,
            on="date",
            how="left"
        )
        .merge(
            event_daily,
            on="date",
            how="left"
        )
    )

    analysis["hourly_data_missing"] = (
        analysis["hourly_records"].isna()
    )

    analysis["event_log_present"] = (
        analysis["event_count"].notna()
    )

    analysis["event_log_gap"] = (
        (~analysis["event_log_present"])
        &
        (analysis["downtime_h"].fillna(0) > 0)
    )

    # ==================================================
    # 6. ROBUST OUTLIER THRESHOLDS
    # ==================================================

    (
        ratio_q1,
        ratio_q3,
        ratio_lower,
        ratio_upper,
    ) = iqr_limits(
        analysis["operating_ratio"]
    )

    (
        downtime_q1,
        downtime_q3,
        downtime_lower,
        downtime_upper,
    ) = iqr_limits(
        analysis["downtime_h"]
    )

    (
        event_q1,
        event_q3,
        event_lower,
        event_upper,
    ) = iqr_limits(
        analysis.loc[
            analysis["event_log_present"],
            "event_count"
        ]
    )

    analysis["low_operating_ratio_outlier"] = (
        analysis["operating_ratio"]
        < ratio_lower
    )

    analysis["high_downtime_outlier"] = (
        analysis["downtime_h"]
        > downtime_upper
    )

    analysis["high_event_count_outlier"] = (
        analysis["event_count"]
        > event_upper
    )

    analysis["outlier_flag_count"] = (
        analysis[
            [
                "low_operating_ratio_outlier",
                "high_downtime_outlier",
                "high_event_count_outlier",
            ]
        ]
        .fillna(False)
        .sum(axis=1)
    )

    # ==================================================
    # 7. RELATIVE SCREENING SCORE
    # ==================================================
    #
    # This is NOT a control limit.
    # It ranks only complete and comparable production days.
    #
    # Days with missing hourly or event-log data are
    # excluded from operational ranking and handled
    # separately as data-quality exceptions.
    # ==================================================

    analysis["operating_loss"] = (
        1 - analysis["operating_ratio"]
    )

    analysis["complete_for_ranking"] = (
        (~analysis["hourly_data_missing"])
        & analysis["event_log_present"]
    )

    valid = analysis[
        analysis["complete_for_ranking"]
    ].copy()

    valid["operating_loss_pct"] = (
        valid["operating_loss"]
        .rank(
            pct=True,
            method="average"
        )
    )

    valid["downtime_pct"] = (
        valid["downtime_h"]
        .rank(
            pct=True,
            method="average"
        )
    )

    valid["event_count_pct"] = (
        valid["event_count"]
        .rank(
            pct=True,
            method="average"
        )
    )

    valid["screening_score"] = (
        valid[
            [
                "operating_loss_pct",
                "downtime_pct",
                "event_count_pct",
            ]
        ]
        .mean(axis=1)
        * 100
    )

    valid["screening_rank"] = (
        valid["screening_score"]
        .rank(
            ascending=False,
            method="min"
        )
        .astype(int)
    )

    analysis = analysis.merge(
        valid[
            [
                "date",
                "operating_loss_pct",
                "downtime_pct",
                "event_count_pct",
                "screening_score",
                "screening_rank",
            ]
        ],
        on="date",
        how="left"
    )

    # ==================================================
    # 8. PRODUCT-LEVEL COMPARISON
    # ==================================================
    #
    # Compare only single-product days.
    # Downtime is NOT attributed directly to product type.
    # ==================================================

    single_product_daily = daily[
        ~daily["multi_product_day"]
    ].copy()

    product_comparison = (
        single_product_daily
        .groupby("product_type_l")
        .agg(
            production_records=(
                "date",
                "count"
            ),
            median_production_units=(
                "production_units",
                "median"
            ),
            mean_production_units=(
                "production_units",
                "mean"
            ),
            median_operating_ratio=(
                "operating_ratio",
                "median"
            ),
            mean_operating_ratio=(
                "operating_ratio",
                "mean"
            ),
            median_nonoperation_h=(
                "derived_nonoperation_h",
                "median"
            ),
        )
        .reset_index()
    )

    # ==================================================
    # 9. EVENT DURATION DISTRIBUTION
    # ==================================================

    event_quantiles = (
        events["downtime_minutes"]
        .quantile(
            [
                0.50,
                0.75,
                0.90,
                0.95,
                0.99,
            ]
        )
    )

    p90_event = events[
        "downtime_minutes"
    ].quantile(0.90)

    long_events = (
        events[
            events["downtime_minutes"]
            >= p90_event
        ]
        .sort_values(
            "downtime_minutes",
            ascending=False
        )
        .copy()
    )

    # ==================================================
    # 10. SAVE RESULTS
    # ==================================================

    analysis_path = (
        results_dir
        / "v2_daily_kpi_screening.csv"
    )

    product_path = (
        results_dir
        / "v2_product_comparison.csv"
    )

    long_event_path = (
        results_dir
        / "v2_long_downtime_events.csv"
    )

    analysis.to_csv(
        analysis_path,
        index=False
    )

    product_comparison.to_csv(
        product_path,
        index=False
    )

    long_events.to_csv(
        long_event_path,
        index=False
    )

    # ==================================================
    # 11. PRINT ANALYSIS
    # ==================================================

    print("\n" + "=" * 70)
    print("V2 OPERATIONS ANALYSIS")
    print("=" * 70)

    print("\n--- IQR-BASED OUTLIER LIMITS ---")
    print(
        f"Operating Ratio lower limit: "
        f"{ratio_lower:.4f}"
    )
    print(
        f"Downtime upper limit (h): "
        f"{downtime_upper:.4f}"
    )
    print(
        f"Event Count upper limit: "
        f"{event_upper:.2f}"
    )

    print(
        "\nOutlier days:",
        (analysis["outlier_flag_count"] > 0).sum()
    )

    print("\n--- TOP 10 SCREENING DAYS ---")

    screening_columns = [
        "screening_rank",
        "date",
        "product_mix_l",
        "production_units",
        "operating_ratio",
        "downtime_h",
        "event_count",
        "screening_score",
        "outlier_flag_count",
    ]

    ranked_analysis = (
        analysis[
            analysis["complete_for_ranking"]
        ]
        .sort_values(
            [
                "screening_rank",
                "date"
            ]
        )
        .copy()
    )

    ranked_analysis["screening_rank"] = (
        ranked_analysis["screening_rank"]
        .astype(int)
    )

    display_screening = ranked_analysis[
        screening_columns
    ].head(10).copy()

    display_screening["date"] = (
        display_screening["date"]
        .dt.strftime("%Y-%m-%d")
    )

    numeric_display_columns = [
        "operating_ratio",
        "downtime_h",
        "event_count",
        "screening_score",
    ]

    display_screening[numeric_display_columns] = (
        display_screening[numeric_display_columns]
        .round(4)
    )

    print(
        display_screening
        .to_string(index=False)
    )

    print("\n--- PRODUCT COMPARISON (SINGLE-PRODUCT DAYS ONLY) ---")
    print(
        product_comparison
        .round(4)
        .to_string(index=False)
    )

    print("\n--- DOWNTIME EVENT DURATION ---")
    print(
        event_quantiles
        .round(3)
        .to_string()
    )

    print(
        f"\nEvents >= P90 "
        f"({p90_event:.2f} min): "
        f"{len(long_events)}"
    )

    print("\n--- DATA QUALITY FLAGS ---")
    print(
        "Missing hourly days:",
        analysis["hourly_data_missing"].sum()
    )
    print(
        "Potential event-log gaps:",
        analysis["event_log_gap"].sum()
    )

    print("\nFiles created:")
    print(analysis_path)
    print(product_path)
    print(long_event_path)


if __name__ == "__main__":
    main()
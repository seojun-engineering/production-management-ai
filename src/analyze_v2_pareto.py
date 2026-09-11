from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def main():
    base_dir = Path(__file__).resolve().parent.parent

    processed_dir = base_dir / "data" / "processed"
    results_dir = base_dir / "results"
    figures_dir = results_dir / "figures"

    figures_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # ==================================================
    # 1. LOAD DATA
    # ==================================================

    events = pd.read_csv(
        processed_dir / "v2_downtime_events.csv"
    )

    daily = pd.read_csv(
        results_dir / "v2_daily_kpi_screening.csv"
    )

    events["date"] = pd.to_datetime(
        events["date"]
    )

    daily["date"] = pd.to_datetime(
        daily["date"]
    )

    # ==================================================
    # 2. EVENT DURATION PARETO
    # ==================================================
    #
    # IMPORTANT:
    # This analysis uses downtime EVENT-LOG duration.
    # It is not treated as canonical equipment downtime
    # because event-log duration and hourly downtime
    # were not consistently reconciled.
    # ==================================================

    event_sorted = (
        events
        .sort_values(
            "downtime_minutes",
            ascending=False
        )
        .reset_index(drop=True)
        .copy()
    )

    total_events = len(event_sorted)

    total_event_minutes = (
        event_sorted["downtime_minutes"].sum()
    )

    event_sorted["event_rank"] = (
        np.arange(1, total_events + 1)
    )

    event_sorted["event_pct"] = (
        event_sorted["event_rank"]
        / total_events
        * 100
    )

    event_sorted["cumulative_minutes"] = (
        event_sorted["downtime_minutes"]
        .cumsum()
    )

    event_sorted["cumulative_duration_pct"] = (
        event_sorted["cumulative_minutes"]
        / total_event_minutes
        * 100
    )

    # ==================================================
    # 3. TOP 10% EVENT CONTRIBUTION
    # ==================================================

    p90_duration = (
        events["downtime_minutes"]
        .quantile(0.90)
    )

    top10_events = events[
        events["downtime_minutes"]
        >= p90_duration
    ].copy()

    top10_minutes = (
        top10_events["downtime_minutes"]
        .sum()
    )

    top10_share = (
        top10_minutes
        / total_event_minutes
        * 100
    )

    # Number of events required to explain
    # 50% and 80% of event-log duration

    events_to_50 = (
        event_sorted[
            event_sorted[
                "cumulative_duration_pct"
            ] >= 50
        ]
        .index[0]
        + 1
    )

    events_to_80 = (
        event_sorted[
            event_sorted[
                "cumulative_duration_pct"
            ] >= 80
        ]
        .index[0]
        + 1
    )

    # ==================================================
    # 4. EVENT DURATION GROUPS
    # ==================================================

    p50 = events[
        "downtime_minutes"
    ].quantile(0.50)

    p90 = events[
        "downtime_minutes"
    ].quantile(0.90)

    events["duration_group"] = pd.cut(
        events["downtime_minutes"],
        bins=[
            -np.inf,
            p50,
            p90,
            np.inf
        ],
        labels=[
            "Short (<=P50)",
            "Medium (P50-P90)",
            "Long (>=P90)"
        ],
        include_lowest=True
    )

    duration_group_summary = (
        events
        .groupby(
            "duration_group",
            observed=False
        )
        .agg(
            event_count=(
                "downtime_id",
                "count"
            ),
            total_minutes=(
                "downtime_minutes",
                "sum"
            ),
            median_minutes=(
                "downtime_minutes",
                "median"
            ),
        )
        .reset_index()
    )

    duration_group_summary[
        "event_share_pct"
    ] = (
        duration_group_summary[
            "event_count"
        ]
        / total_events
        * 100
    )

    duration_group_summary[
        "duration_share_pct"
    ] = (
        duration_group_summary[
            "total_minutes"
        ]
        / total_event_minutes
        * 100
    )

    # ==================================================
    # 5. OUTLIER DAYS
    # ==================================================

    outlier_days = (
        daily[
            daily["outlier_flag_count"] > 0
        ][
            [
                "date",
                "product_mix_l",
                "operating_ratio",
                "downtime_h",
                "event_count",
                "screening_rank",
                "screening_score",
                "outlier_flag_count",
            ]
        ]
        .sort_values(
            "screening_rank"
        )
    )

    # ==================================================
    # 6. SAVE SUMMARY TABLES
    # ==================================================

    pareto_path = (
        results_dir
        / "v2_downtime_event_pareto.csv"
    )

    group_path = (
        results_dir
        / "v2_downtime_duration_groups.csv"
    )

    outlier_path = (
        results_dir
        / "v2_outlier_days.csv"
    )

    event_sorted.to_csv(
        pareto_path,
        index=False
    )

    duration_group_summary.to_csv(
        group_path,
        index=False
    )

    outlier_days.to_csv(
        outlier_path,
        index=False
    )

    # ==================================================
    # 7. FIGURE 1 — EVENT PARETO CURVE
    # ==================================================

    plt.figure(
        figsize=(9, 5)
    )

    plt.plot(
        event_sorted["event_pct"],
        event_sorted[
            "cumulative_duration_pct"
        ]
    )

    plt.axhline(
        80,
        linestyle="--"
    )

    plt.axvline(
        10,
        linestyle="--"
    )

    plt.xlabel(
        "Cumulative Share of Downtime Events (%)"
    )

    plt.ylabel(
        "Cumulative Share of Event-Log Duration (%)"
    )

    plt.title(
        "Downtime Event Duration Pareto"
    )

    plt.tight_layout()

    plt.savefig(
        figures_dir
        / "v2_downtime_pareto.png",
        dpi=200
    )

    plt.close()

    # ==================================================
    # 8. FIGURE 2 — TOP SCREENING DAYS
    # ==================================================

    ranked = (
        daily[
            daily["screening_rank"]
            .notna()
        ]
        .sort_values(
            "screening_rank"
        )
        .head(10)
        .copy()
    )

    ranked["date_label"] = (
        ranked["date"]
        .dt.strftime("%Y-%m-%d")
    )

    plt.figure(
        figsize=(10, 5)
    )

    plt.bar(
        ranked["date_label"],
        ranked["screening_score"]
    )

    plt.xticks(
        rotation=45,
        ha="right"
    )

    plt.xlabel(
        "Production Date"
    )

    plt.ylabel(
        "Relative Screening Score"
    )

    plt.title(
        "Top 10 Operational Screening Days"
    )

    plt.tight_layout()

    plt.savefig(
        figures_dir
        / "v2_top_screening_days.png",
        dpi=200
    )

    plt.close()

    # ==================================================
    # 9. FIGURE 3 — OPERATING RATIO VS DOWNTIME
    # ==================================================

    complete = daily[
        daily["complete_for_ranking"]
        == True
    ].copy()

    plt.figure(
        figsize=(8, 6)
    )

    plt.scatter(
        complete["downtime_h"],
        complete["operating_ratio"]
    )

    top5 = (
        complete
        .sort_values(
            "screening_rank"
        )
        .head(5)
    )

    for _, row in top5.iterrows():

        plt.annotate(
            row["date"].strftime(
                "%Y-%m-%d"
            ),
            (
                row["downtime_h"],
                row["operating_ratio"]
            )
        )

    plt.xlabel(
        "Hourly-record Downtime (h)"
    )

    plt.ylabel(
        "Operating Ratio"
    )

    plt.title(
        "Operating Ratio vs Downtime"
    )

    plt.tight_layout()

    plt.savefig(
        figures_dir
        / "v2_operating_ratio_vs_downtime.png",
        dpi=200
    )

    plt.close()

    # ==================================================
    # 10. PRINT SUMMARY
    # ==================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        "V2 DOWNTIME PARETO ANALYSIS"
    )

    print(
        "=" * 70
    )

    print(
        f"\nTotal downtime events: "
        f"{total_events}"
    )

    print(
        f"Total event-log duration: "
        f"{total_event_minutes:.2f} min"
    )

    print(
        f"\nP90 duration threshold: "
        f"{p90_duration:.2f} min"
    )

    print(
        f"Events >= P90: "
        f"{len(top10_events)}"
    )

    print(
        f"Share of total event-log duration "
        f"from P90+ events: "
        f"{top10_share:.2f}%"
    )

    print(
        f"\nEvents required to explain "
        f"50% of event-log duration: "
        f"{events_to_50}"
    )

    print(
        f"Events required to explain "
        f"80% of event-log duration: "
        f"{events_to_80}"
    )

    print(
        "\n--- DURATION GROUP SUMMARY ---"
    )

    print(
        duration_group_summary
        .round(2)
        .to_string(index=False)
    )

    print(
        "\n--- STATISTICAL OUTLIER DAYS ---"
    )

    display_outliers = outlier_days.copy()

numeric_cols = display_outliers.select_dtypes(
    include="number"
).columns

display_outliers[numeric_cols] = (
    display_outliers[numeric_cols].round(4)
)

print(
    display_outliers.to_string(
        index=False
    )
)

    print(
        "\nFigures created:"
    )

    print(
        figures_dir
        / "v2_downtime_pareto.png"
    )

    print(
        figures_dir
        / "v2_top_screening_days.png"
    )

    print(
        figures_dir
        / "v2_operating_ratio_vs_downtime.png"
    )


if __name__ == "__main__":
    main()
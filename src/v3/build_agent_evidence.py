from pathlib import Path
import json

import pandas as pd


def records(df: pd.DataFrame):
    """
    Convert DataFrame to JSON-safe Python records.
    NaN -> null, Timestamp -> ISO string.
    """
    return json.loads(
        df.to_json(
            orient="records",
            date_format="iso"
        )
    )


def save_json(data, path: Path):
    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


def main():
    base_dir = Path(__file__).resolve().parents[2]

    processed_dir = (
        base_dir
        / "data"
        / "processed"
    )

    results_dir = (
        base_dir
        / "results"
    )

    output_dir = (
        results_dir
        / "v3"
        / "evidence"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # ==================================================
    # 1. LOAD VERIFIED V2 DATA
    # ==================================================

    daily = pd.read_csv(
        results_dir
        / "v2_daily_kpi_screening.csv"
    )

    product = pd.read_csv(
        results_dir
        / "v2_product_comparison.csv"
    )

    duration_groups = pd.read_csv(
        results_dir
        / "v2_downtime_duration_groups.csv"
    )

    outlier_days = pd.read_csv(
        results_dir
        / "v2_outlier_days.csv"
    )

    hourly = pd.read_csv(
        processed_dir
        / "v2_hourly_operation.csv"
    )

    events = pd.read_csv(
        processed_dir
        / "v2_downtime_events.csv"
    )

    daily["date"] = pd.to_datetime(
        daily["date"]
    )

    hourly["date"] = pd.to_datetime(
        hourly["date"]
    )

    events["date"] = pd.to_datetime(
        events["date"]
    )

    # ==================================================
    # 2. COMMON DATA QUALITY / LIMITATIONS
    # ==================================================

    common = {
        "dataset": {
            "daily_production_records": 59,
            "hourly_operation_records": 265,
            "downtime_events": 1388,
            "production_period": {
                "start": "2022-07-22",
                "end": "2023-02-10"
            }
        },

        "data_quality": {
            "corrected_downtime_date_rows": 18,
            "missing_hourly_days": int(
                daily["hourly_data_missing"].sum()
            ),
            "potential_event_log_gaps": int(
                daily["event_log_gap"].sum()
            )
        },

        "analysis_rules": [
            "Python performs all numerical calculations.",
            "Agents must not recalculate KPI values.",
            "Agents must not invent physical root causes.",
            "Screening score is a relative ranking, not a control limit.",
            "Event-log duration is diagnostic and is not treated as canonical equipment downtime.",
            "Product type correlation must not be described as causation."
        ]
    }

    # ==================================================
    # 3. PRODUCTION AGENT EVIDENCE
    # ==================================================

    ranked = (
        daily[
            daily["screening_rank"].notna()
        ]
        .sort_values(
            "screening_rank"
        )
    )

    production_columns = [
        "date",
        "product_mix_l",
        "production_units",
        "operating_ratio",
        "downtime_h",
        "event_count",
        "screening_rank",
        "screening_score"
    ]

    production_evidence = {
        "agent": "production",

        "purpose": (
            "Identify production days requiring "
            "operational review using verified V2 metrics."
        ),

        "common": common,

        "top_screening_days": records(
            ranked[
                production_columns
            ].head(10)
        ),

        "product_comparison_single_product_days": (
            records(product)
        ),

        "production_unit_distribution": {
            "median": float(
                daily[
                    "production_units"
                ].median()
            ),
            "mean": float(
                daily[
                    "production_units"
                ].mean()
            ),
            "min": int(
                daily[
                    "production_units"
                ].min()
            ),
            "max": int(
                daily[
                    "production_units"
                ].max()
            )
        }
    }

    # ==================================================
    # 4. DOWNTIME AGENT EVIDENCE
    # ==================================================

    longest_events = (
        events
        .sort_values(
            "downtime_minutes",
            ascending=False
        )
        .head(15)
    )

    downtime_columns = [
        "downtime_id",
        "date",
        "downtime_start_time",
        "downtime_end_time",
        "downtime_minutes"
    ]

    total_event_minutes = float(
        events[
            "downtime_minutes"
        ].sum()
    )

    p90 = float(
        events[
            "downtime_minutes"
        ].quantile(0.90)
    )

    p90_events = events[
        events["downtime_minutes"] >= p90
    ]

    p90_duration_share = (
        p90_events[
            "downtime_minutes"
        ].sum()
        / total_event_minutes
        * 100
    )

    downtime_evidence = {
        "agent": "downtime",

        "purpose": (
            "Analyze downtime concentration, "
            "frequency, and long-duration events."
        ),

        "common": common,

        "event_summary": {
            "total_events": int(
                len(events)
            ),
            "total_event_log_minutes": round(
                total_event_minutes,
                2
            ),
            "median_event_minutes": round(
                float(
                    events[
                        "downtime_minutes"
                    ].median()
                ),
                3
            ),
            "p90_event_minutes": round(
                p90,
                3
            ),
            "p90_plus_event_count": int(
                len(p90_events)
            ),
            "p90_plus_duration_share_pct": round(
                float(
                    p90_duration_share
                ),
                2
            )
        },

        "duration_groups": records(
            duration_groups
        ),

        "statistical_outlier_days": records(
            outlier_days
        ),

        "longest_events": records(
            longest_events[
                downtime_columns
            ]
        )
    }

    # ==================================================
    # 5. EFFICIENCY AGENT EVIDENCE
    # ==================================================

    complete = daily[
        daily["complete_for_ranking"] == True
    ].copy()

    lowest_ratio_days = (
        complete
        .sort_values(
            "operating_ratio"
        )
        .head(10)
    )

    ratio_columns = [
        "date",
        "product_mix_l",
        "production_units",
        "operating_ratio",
        "downtime_h",
        "event_count",
        "screening_rank"
    ]

    efficiency_evidence = {
        "agent": "efficiency",

        "purpose": (
            "Evaluate operating-ratio loss "
            "without inventing its physical cause."
        ),

        "common": common,

        "daily_operating_ratio_distribution": {
            "p10": round(
                float(
                    complete[
                        "operating_ratio"
                    ].quantile(0.10)
                ),
                4
            ),
            "p25": round(
                float(
                    complete[
                        "operating_ratio"
                    ].quantile(0.25)
                ),
                4
            ),
            "median": round(
                float(
                    complete[
                        "operating_ratio"
                    ].median()
                ),
                4
            ),
            "p75": round(
                float(
                    complete[
                        "operating_ratio"
                    ].quantile(0.75)
                ),
                4
            ),
            "p90": round(
                float(
                    complete[
                        "operating_ratio"
                    ].quantile(0.90)
                ),
                4
            )
        },

        "lowest_operating_ratio_days": records(
            lowest_ratio_days[
                ratio_columns
            ]
        ),

        "product_comparison_single_product_days": (
            records(product)
        )
    }

    # ==================================================
    # 6. PATTERN AGENT EVIDENCE
    # ==================================================

    hourly_pattern = (
        hourly
        .groupby("hour_start")
        .agg(
            records=(
                "date",
                "count"
            ),
            mean_operating_ratio=(
                "operating_ratio",
                "mean"
            ),
            median_operating_ratio=(
                "operating_ratio",
                "median"
            ),
            mean_downtime_h=(
                "downtime_h",
                "mean"
            ),
            total_downtime_h=(
                "downtime_h",
                "sum"
            )
        )
        .reset_index()
        .sort_values(
            "hour_start"
        )
    )

    # Extract hour from source event time.
    events["event_start_hour"] = pd.to_numeric(
        events[
            "downtime_start_time"
        ]
        .astype(str)
        .str.slice(0, 2),
        errors="coerce"
    )

    event_hour_pattern = (
        events
        .groupby(
            "event_start_hour"
        )
        .agg(
            event_count=(
                "downtime_id",
                "count"
            ),
            median_event_minutes=(
                "downtime_minutes",
                "median"
            ),
            total_event_minutes=(
                "downtime_minutes",
                "sum"
            )
        )
        .reset_index()
        .sort_values(
            "event_start_hour"
        )
    )

    daily["weekday"] = (
        daily["date"]
        .dt.day_name()
    )

    weekday_pattern = (
        daily[
            daily[
                "complete_for_ranking"
            ] == True
        ]
        .groupby("weekday")
        .agg(
            production_days=(
                "date",
                "count"
            ),
            median_operating_ratio=(
                "operating_ratio",
                "median"
            ),
            mean_downtime_h=(
                "downtime_h",
                "mean"
            ),
            mean_event_count=(
                "event_count",
                "mean"
            )
        )
        .reset_index()
    )

    pattern_evidence = {
        "agent": "pattern",

        "purpose": (
            "Identify repeated temporal patterns "
            "without treating correlation as root cause."
        ),

        "common": common,

        "hourly_operation_pattern": records(
            hourly_pattern
        ),

        "downtime_event_start_hour_pattern": records(
            event_hour_pattern
        ),

        "weekday_pattern": records(
            weekday_pattern
        )
    }

    # ==================================================
    # 7. SAVE
    # ==================================================

    files = {
        "production_evidence.json":
            production_evidence,

        "downtime_evidence.json":
            downtime_evidence,

        "efficiency_evidence.json":
            efficiency_evidence,

        "pattern_evidence.json":
            pattern_evidence
    }

    for filename, payload in files.items():
        save_json(
            payload,
            output_dir / filename
        )

    print(
        "\n"
        + "=" * 70
    )

    print(
        "V3 AGENT EVIDENCE BUILD"
    )

    print(
        "=" * 70
    )

    for filename in files:
        print(
            output_dir / filename
        )

    print(
        "\nEvidence packages created: "
        f"{len(files)}"
    )


if __name__ == "__main__":
    main()
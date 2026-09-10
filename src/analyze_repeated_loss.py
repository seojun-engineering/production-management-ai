from pathlib import Path
import sys
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))

from calculate_kpi import calculate_kpi
from detect_exceptions import detect_exceptions, build_exception_reason


def analyze_repeated_loss(exceptions: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate repeated exception patterns by product and exception reason.
    """

    summary = (
        exceptions
        .groupby(["product_code", "exception_reason"])
        .size()
        .reset_index(name="occurrence_count")
        .sort_values(
            by="occurrence_count",
            ascending=False
        )
    )

    summary["priority"] = summary["occurrence_count"].apply(
        lambda x: "HIGH" if x >= 3
        else "MEDIUM" if x == 2
        else "LOW"
    )

    return summary


def main():
    base_dir = Path(__file__).resolve().parent.parent

    input_path = (
        base_dir
        / "data"
        / "sample_production_data.csv"
    )

    results_dir = base_dir / "results"
    results_dir.mkdir(exist_ok=True)

    raw_df = pd.read_csv(input_path)

    kpi_df = calculate_kpi(raw_df)
    result = detect_exceptions(kpi_df)

    result["exception_reason"] = result.apply(
        build_exception_reason,
        axis=1
    )

    exceptions = result[result["is_exception"]].copy()

    repeated_summary = analyze_repeated_loss(exceptions)

    # Save detailed exception records
    exception_output = (
        results_dir
        / "exception_summary.csv"
    )

    exceptions.to_csv(
        exception_output,
        index=False
    )

    # Save repeated-loss analysis
    repeated_output = (
        results_dir
        / "repeated_loss_summary.csv"
    )

    repeated_summary.to_csv(
        repeated_output,
        index=False
    )

    print("\n=== Repeated Loss Analysis ===\n")
    print(repeated_summary.to_string(index=False))

    print("\nFiles saved:")
    print(exception_output)
    print(repeated_output)


if __name__ == "__main__":
    main()
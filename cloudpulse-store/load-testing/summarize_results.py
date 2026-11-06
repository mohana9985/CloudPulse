import csv
import sys
from pathlib import Path


def main(folder: str) -> None:
    files = sorted(Path(folder).glob("*_stats.csv"))
    if not files:
        print(f"No *_stats.csv files found in {folder}")
        return

    print("| Scenario | Total requests | Failure % | Requests/s | Avg (ms) | Median (ms) | 95th pct (ms) |")
    print("|---|---|---|---|---|---|---|")
    for path in files:
        with path.open(newline="") as fh:
            row = next((r for r in csv.DictReader(fh) if r["Name"] == "Aggregated"), None)
        if row is None:
            continue
        total = int(row["Request Count"])
        failures = int(row["Failure Count"])
        failure_pct = (failures / total * 100) if total else 0.0
        print(
            f"| {path.name.removesuffix('_stats.csv')} | {total} | {failure_pct:.2f} | "
            f"{float(row['Requests/s']):.2f} | {float(row['Average Response Time']):.1f} | "
            f"{row['Median Response Time']} | {row['95%']} |"
        )


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results")

import csv
import json
import sys
from pathlib import Path

ORDER = ["round_robin", "weighted_round_robin", "least_loaded", "shortest_job_first", "fcfs_baseline"]
SHORT = {"round_robin": "RR", "weighted_round_robin": "WRR", "least_loaded": "LL",
         "shortest_job_first": "SJF", "fcfs_baseline": "FCFS (control)"}


def main(folder: str) -> None:
    out = Path(folder)
    rows = []
    for alg in ORDER:
        stats = out / f"{alg}_stats.csv"
        gw = out / f"{alg}.gateway.json"
        if not stats.exists() or not gw.exists():
            continue
        with stats.open(newline="") as fh:
            agg = next((r for r in csv.DictReader(fh) if r["Name"] == "Aggregated"), None)
        if agg is None:
            continue
        g = json.loads(gw.read_text())
        total = int(agg["Request Count"])
        fail = int(agg["Failure Count"])
        share = g["share_per_backend"]
        rows.append((
            SHORT[alg], total, f"{(fail / total * 100) if total else 0:.2f}", f"{float(agg['Requests/s']):.2f}",
            f"{float(agg['Average Response Time']):.1f}", agg["Median Response Time"], agg["95%"],
            f"{g['avg_wait_ms'] or 0:.1f}", f"{g['avg_service_ms'] or 0:.1f}",
            " / ".join(f"{share.get(k, 0):.0f}" for k in ("B1", "B2", "B3")),
        ))
    print("| Algorithm | Requests | Fail % | Req/s | Avg ms | Median ms | p95 ms | Gateway queue wait ms | Backend service ms | Share B1 / B2 / B3 % |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print("| " + " | ".join(str(x) for x in r) + " |")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results")

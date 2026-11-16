from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src.schedulers import DISPLAY_NAMES  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ORDER = ["round_robin", "weighted_round_robin", "least_loaded", "shortest_job_first", "fcfs_baseline"]
COLORS = {"round_robin": "#4C72B0", "weighted_round_robin": "#55A868", "least_loaded": "#C44E52",
          "shortest_job_first": "#8172B2", "fcfs_baseline": "#937860"}
NOTE = "REAL execution on live Docker workers (CPU quotas 0.75/0.45/0.30). Mean ± SD over seeds."


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def f(x):
    return None if x in (None, "", "None") else float(x)


def ms(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, None
    return statistics.fmean(vals), (statistics.stdev(vals) if len(vals) > 1 else 0.0)


def summarise(rows: list[dict], group: tuple[str, ...], metrics: list[str]) -> list[dict]:
    g = defaultdict(list)
    for r in rows:
        g[tuple(r[k] for k in group)].append(r)
    out = []
    for key, rs in g.items():
        row = dict(zip(group, key))
        row["runs"] = len(rs)
        for m in metrics:
            mean, sd = ms([f(r.get(m)) for r in rs])
            row[f"{m}_mean"] = None if mean is None else round(mean, 4)
            row[f"{m}_sd"] = None if sd is None else round(sd, 4)
        out.append(row)
    return sorted(out, key=lambda r: tuple(
        ORDER.index(r[k]) if k == "algorithm" else (int(r[k]) if r[k].isdigit() else r[k]) for k in group))


def write_csv(path: Path, rows: list[dict]) -> None:
    if rows:
        with path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


def grouped_bar(ax, summary, xkey, metric, title, ylabel):
    xs = sorted({r[xkey] for r in summary}, key=lambda v: int(v) if v.isdigit() else v)
    algs = [a for a in ORDER if any(r["algorithm"] == a for r in summary)]
    width = 0.8 / max(1, len(algs))
    for i, alg in enumerate(algs):
        vals, errs = [], []
        for x in xs:
            r = next((r for r in summary if r["algorithm"] == alg and r[xkey] == x), None)
            vals.append(r[f"{metric}_mean"] if r and r[f"{metric}_mean"] is not None else 0)
            errs.append(r[f"{metric}_sd"] if r and r[f"{metric}_sd"] is not None else 0)
        ax.bar([j + i * width for j in range(len(xs))], vals, width, yerr=errs, capsize=3,
               label=DISPLAY_NAMES[alg], color=COLORS[alg])
    ax.set_xticks([j + width * (len(algs) - 1) / 2 for j in range(len(xs))], xs)
    ax.set_xlabel(xkey)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.3)


def save(fig, path: Path) -> None:
    fig.text(0.5, 0.01, NOTE, ha="center", fontsize=8, color="#555")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("experiment_id")
    a = p.parse_args()
    res = ROOT / "results" / a.experiment_id
    charts = ROOT / "charts" / a.experiment_id
    charts.mkdir(parents=True, exist_ok=True)
    metrics = ["makespan_s", "throughput_tps", "avg_exec_s", "avg_wait_s", "p95_wait_s", "max_wait_s",
               "avg_turnaround_s", "avg_net_overhead_ms", "retries", "lost"]

    grid = read(res / "runs_grid.csv")
    if grid:
        s = summarise(grid, ("algorithm", "size"), metrics)
        write_csv(res / "algorithm_summary.csv", s)
        for metric, title, ylabel, name in [
            ("avg_turnaround_s", "Average turnaround time", "seconds", "01_avg_turnaround"),
            ("avg_wait_s", "Average waiting time", "seconds", "02_avg_wait"),
            ("throughput_tps", "Throughput", "tasks / second", "03_throughput"),
            ("makespan_s", "Makespan", "seconds", "04_makespan"),
            ("max_wait_s", "Maximum waiting time", "seconds", "05_max_wait"),
            ("avg_net_overhead_ms", "Coordinator↔worker overhead per task", "milliseconds", "06_overhead"),
        ]:
            fig, ax = plt.subplots(figsize=(9, 4.8))
            grouped_bar(ax, s, "size", metric, f"{title} by workload size (live)", ylabel)
            ax.legend(fontsize=8)
            save(fig, charts / f"{name}.png")
        pw = read(res / "per_worker_grid.csv")
        if pw:
            ws = summarise(pw, ("algorithm", "worker_id"), ["share_pct", "utilisation_pct", "mean_cpu_pct_of_limit",
                                                            "mean_memory_mb", "max_memory_mb"])
            write_csv(res / "per_worker_summary.csv", ws)
            for metric, title, ylabel, name in [
                ("share_pct", "Task distribution across workers", "% of completed tasks", "07_task_share"),
                ("mean_cpu_pct_of_limit", "Measured CPU (psutil) during runs", "% of container CPU limit",
                 "08_cpu"),
                ("mean_memory_mb", "Measured container memory during runs", "MB", "09_memory"),
            ]:
                fig, ax = plt.subplots(figsize=(9, 4.8))
                grouped_bar(ax, ws, "worker_id", metric, title + " (all sizes)", ylabel)
                ax.legend(fontsize=8)
                save(fig, charts / f"{name}.png")

    normal, failure = read(res / "runs_normal.csv"), read(res / "runs_failure.csv")
    if normal and failure:
        fm = metrics + ["detected_failed_after_kill_s", "unavailable_after_kill_s", "affected_recovered_s",
                        "interrupted_tasks", "reassigned_queued_tasks", "worker_rejoined_after_kill_s"]
        sn = summarise(normal, ("algorithm",), metrics)
        sf = summarise(failure, ("algorithm",), fm)
        for r in sn:
            r["scenario"] = "normal"
        for r in sf:
            r["scenario"] = "one worker killed"
        write_csv(res / "failure_summary.csv", sf)
        write_csv(res / "normal_summary.csv", sn)
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
        for ax, metric, ylabel in [(axes[0], "avg_turnaround_s", "avg turnaround (s)"),
                                   (axes[1], "makespan_s", "makespan (s)")]:
            algs = [x for x in ORDER if any(r["algorithm"] == x for r in sn)]
            xs = range(len(algs))
            for k, (rows, lab, col) in enumerate([(sn, "normal", "#4C72B0"), (sf, "W2 killed", "#C44E52")]):
                vals = [next(r for r in rows if r["algorithm"] == x)[f"{metric}_mean"] for x in algs]
                errs = [next(r for r in rows if r["algorithm"] == x)[f"{metric}_sd"] for x in algs]
                ax.bar([i + k * 0.4 for i in xs], vals, 0.4, yerr=errs, capsize=3, label=lab, color=col)
            ax.set_xticks([i + 0.2 for i in xs], [DISPLAY_NAMES[x] for x in algs], fontsize=8)
            ax.set_ylabel(ylabel)
            ax.grid(axis="y", alpha=0.3)
            ax.legend(fontsize=8)
        fig.suptitle("Normal execution vs one worker crashed (docker kill) and restarted")
        save(fig, charts / "10_failure_vs_normal.png")

    scaling = read(res / "runs_scaling.csv")
    if scaling:
        s = summarise(scaling, ("algorithm", "workers"), metrics)
        write_csv(res / "scaling_summary.csv", s)
        for metric, ylabel, name in [("makespan_s", "makespan (s)", "11_scaling_makespan"),
                                     ("avg_turnaround_s", "avg turnaround (s)", "12_scaling_turnaround")]:
            fig, ax = plt.subplots(figsize=(9, 4.8))
            grouped_bar(ax, s, "workers", metric, "Same workload on 1, 2 and 3 workers", ylabel)
            ax.legend(fontsize=8)
            save(fig, charts / f"{name}.png")
    print(f"charts -> charts/{a.experiment_id}/ ; summaries -> results/{a.experiment_id}/")


if __name__ == "__main__":
    main()

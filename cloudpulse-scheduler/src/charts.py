from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import matplotlib

matplotlib.use("Agg")  # headless: no display needed (EC2 / Docker)
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from .schedulers import DISPLAY_NAMES  # noqa: E402

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
COLORS = {
    "round_robin": "#2a78d6",
    "weighted_round_robin": "#eb6834",
    "least_loaded": "#1baf7a",
    "shortest_job_first": "#eda100",
    "fcfs_baseline": "#9a9993",
}
HATCH = {"fcfs_baseline": "///"}
WORKER_COLORS = ["#104281", "#2a78d6", "#86b6ef", "#b7d3f6", "#cde2fb"]
ORDER = ["round_robin", "weighted_round_robin", "least_loaded", "shortest_job_first", "fcfs_baseline"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": TEXT_2, "text.color": TEXT,
    "xtick.color": TEXT_2, "ytick.color": TEXT_2, "axes.grid": True, "axes.grid.axis": "y",
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
    "axes.titlesize": 11, "axes.titleweight": "bold", "hatch.color": SURFACE, "hatch.linewidth": 1.2,
})


def _label(name: str) -> str:
    return DISPLAY_NAMES.get(name, name)


def _algos(agg: Sequence[Mapping]) -> list[str]:
    present = {a["algorithm"] for a in agg}
    return [a for a in ORDER if a in present]


def _cells(agg):
    sizes = sorted({a["workload_size"] for a in agg})
    loads = sorted({(a["target_utilisation"], a["load_condition"]) for a in agg})
    return sizes, [l for _, l in loads], {l: t for t, l in loads}


def _legend(fig, algos, extra: str = ""):
    handles = [Patch(facecolor=COLORS[a], hatch=HATCH.get(a, ""), edgecolor=SURFACE, label=_label(a)) for a in algos]
    fig.legend(handles=handles, loc="upper center", ncol=len(handles), frameon=False,
               bbox_to_anchor=(0.5, 0.93), fontsize=9.5)
    if extra:
        fig.text(0.5, 0.015, extra, ha="center", fontsize=8.5, color=TEXT_2)


def _get(agg, size, load, algo):
    return next((a for a in agg if a["workload_size"] == size and a["load_condition"] == load and a["algorithm"] == algo), None)


def metric_chart(agg, key: str, title: str, ylabel: str, path: Path, n_seeds: int) -> Path:
    sizes, loads, targets = _cells(agg)
    algos = _algos(agg)
    fig, axes = plt.subplots(1, len(sizes), figsize=(4.4 * len(sizes) + 0.6, 4.6), squeeze=False)
    width = 0.8 / len(algos)
    for ax, size in zip(axes[0], sizes):
        for i, algo in enumerate(algos):
            xs, ys, es = [], [], []
            for j, load in enumerate(loads):
                a = _get(agg, size, load, algo)
                if a is None:
                    continue
                xs.append(j - 0.4 + width * (i + 0.5))
                ys.append(a[f"{key}_mean"])
                es.append(a[f"{key}_std"])
            ax.bar(xs, ys, width=width, color=COLORS[algo], hatch=HATCH.get(algo, ""), edgecolor=SURFACE, linewidth=1)
            if n_seeds > 1:
                ax.errorbar(xs, ys, yerr=es, fmt="none", ecolor=TEXT_2, elinewidth=0.9, capsize=2)
        ax.set_xticks(range(len(loads)), [f"{l}\n(ρ={targets[l]:.2f})" for l in loads])
        ax.set_title(f"{size} tasks", color=TEXT)
        ax.set_ylabel(ylabel)
        ax.set_ylim(bottom=0)
    fig.suptitle(title, fontsize=13, fontweight="bold", color=TEXT, y=0.995)
    note = (f"Bars: mean across {n_seeds} seeds; whiskers: ±1 SD. " if n_seeds > 1 else "Single seed. ") + \
        "Same workload for every algorithm within a seed. FCFS = control baseline (not ranked). ρ = target utilisation."
    _legend(fig, algos, note)
    fig.tight_layout(rect=(0, 0.04, 1, 0.88))
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def load_distribution_chart(agg, worker_specs, size: int, path: Path, field: str = "work_share_pct",
                            title: str = "Work distribution across workers") -> Path:
    _, loads, targets = _cells(agg)
    algos = _algos(agg)
    wids = [s.worker_id for s in worker_specs]
    total_cap = sum(s.capacity for s in worker_specs if s.available) or 1.0
    fig, axes = plt.subplots(1, len(loads), figsize=(4.6 * len(loads) + 0.6, 4.2), squeeze=False, sharey=True)
    for ax, load in zip(axes[0], loads):
        labels = ["Capacity share\n(reference)"] + [_label(a) for a in algos]
        rows = [[100 * s.capacity / total_cap if s.available else 0 for s in worker_specs]]
        for algo in algos:
            a = _get(agg, size, load, algo)
            rows.append([a[f"{w}_{field}_mean"] if a else 0 for w in wids])
        for r, vals in enumerate(rows):
            left = 0.0
            for k, v in enumerate(vals):
                ax.barh(r, v, left=left, height=0.62, color=WORKER_COLORS[k % len(WORKER_COLORS)],
                        edgecolor=SURFACE, linewidth=2)
                if v >= 9:
                    ax.text(left + v / 2, r, f"{v:.0f}%", ha="center", va="center", fontsize=8,
                            color=SURFACE if k < 2 else TEXT)
                left += v
        ax.set_yticks(range(len(labels)), labels)
        ax.invert_yaxis()
        ax.set_xlim(0, 100)
        ax.set_xlabel("Share of total (%)")
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", visible=True)
        ax.set_title(f"{load} (ρ={targets[load]:.2f})", color=TEXT)
    handles = [Patch(facecolor=WORKER_COLORS[k % len(WORKER_COLORS)], edgecolor=SURFACE,
                     label=f"{s.worker_id} (capacity {s.capacity:g})") for k, s in enumerate(worker_specs)]
    fig.legend(handles=handles, loc="upper center", ncol=len(handles), frameon=False, bbox_to_anchor=(0.5, 0.93))
    fig.suptitle(f"{title} — {size} tasks", fontsize=13, fontweight="bold", color=TEXT, y=0.995)
    fig.text(0.5, 0.015, "Mean across seeds. Top row = each worker's share of total capacity (a capacity-proportional split).",
             ha="center", fontsize=8.5, color=TEXT_2)
    fig.tight_layout(rect=(0, 0.04, 1, 0.88))
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def per_worker_utilisation_chart(agg, worker_specs, size: int, path: Path) -> Path:
    _, loads, targets = _cells(agg)
    algos = _algos(agg)
    wids = [s.worker_id for s in worker_specs]
    fig, axes = plt.subplots(1, len(loads), figsize=(4.6 * len(loads) + 0.6, 4.4), squeeze=False, sharey=True)
    width = 0.8 / len(wids)
    for ax, load in zip(axes[0], loads):
        for k, wid in enumerate(wids):
            xs, ys, es = [], [], []
            for i, algo in enumerate(algos):
                a = _get(agg, size, load, algo)
                xs.append(i - 0.4 + width * (k + 0.5))
                ys.append(a[f"{wid}_utilisation_pct_mean"])
                es.append(a[f"{wid}_utilisation_pct_std"])
            ax.bar(xs, ys, width=width, color=WORKER_COLORS[k % len(WORKER_COLORS)], edgecolor=SURFACE, linewidth=1)
            ax.errorbar(xs, ys, yerr=es, fmt="none", ecolor=TEXT_2, elinewidth=0.9, capsize=2)
        ax.set_xticks(range(len(algos)), [_label(a).replace(" (control)", "\n(control)") for a in algos])
        ax.set_ylim(0, 105)
        ax.set_ylabel("Simulated utilisation (%)")
        ax.set_title(f"{load} (ρ={targets[load]:.2f})", color=TEXT)
    handles = [Patch(facecolor=WORKER_COLORS[k % len(WORKER_COLORS)], label=f"{s.worker_id} (capacity {s.capacity:g})")
               for k, s in enumerate(worker_specs)]
    fig.legend(handles=handles, loc="upper center", ncol=len(handles), frameon=False, bbox_to_anchor=(0.5, 0.93))
    fig.suptitle(f"Per-worker simulated utilisation — {size} tasks", fontsize=13, fontweight="bold", color=TEXT, y=0.995)
    fig.text(0.5, 0.015, "Busy time / makespan per simulated worker; mean ± 1 SD across seeds. Not EC2 CPU utilisation.",
             ha="center", fontsize=8.5, color=TEXT_2)
    fig.tight_layout(rect=(0, 0.04, 1, 0.88))
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def fcfs_vs_sjf_chart(agg, size: int, path: Path, n_seeds: int) -> Path:
    _, loads, targets = _cells(agg)
    pair = ["fcfs_baseline", "shortest_job_first"]
    groups = [("All tasks", "avg_waiting_time", "max_waiting_time"),
              ("Small", "small_avg_waiting_time", "small_max_waiting_time"),
              ("Medium", "medium_avg_waiting_time", "medium_max_waiting_time"),
              ("Large", "large_avg_waiting_time", "large_max_waiting_time")]
    fig, axes = plt.subplots(2, len(loads), figsize=(4.6 * len(loads) + 0.6, 7.6), squeeze=False)
    for row, (ylabel, idx) in enumerate([("Average waiting time (s)", 1), ("Maximum waiting time (s)", 2)]):
        for ax, load in zip(axes[row], loads):
            for i, algo in enumerate(pair):
                a = _get(agg, size, load, algo)
                xs = [g - 0.2 + 0.4 * i for g in range(len(groups))]
                ys = [a[f"{g[idx]}_mean"] for g in groups]
                es = [a[f"{g[idx]}_std"] for g in groups]
                ax.bar(xs, ys, width=0.4, color=COLORS[algo], hatch=HATCH.get(algo, ""), edgecolor=SURFACE, linewidth=1)
                if n_seeds > 1:
                    ax.errorbar(xs, ys, yerr=es, fmt="none", ecolor=TEXT_2, elinewidth=0.9, capsize=2)
            ax.set_xticks(range(len(groups)), [g[0] for g in groups])
            ax.set_ylabel(ylabel)
            ax.set_ylim(bottom=0)
            if row == 0:
                ax.set_title(f"{load} (ρ={targets[load]:.2f})", color=TEXT)
    _legend(fig, pair, f"{size} tasks. Same central queue and same worker choice; only the queue order differs. "
                       f"Mean ± 1 SD across {n_seeds} seeds.")
    fig.suptitle("Effect of shortest-job ordering: FCFS control vs SJF", fontsize=13, fontweight="bold", color=TEXT, y=0.995)
    fig.tight_layout(rect=(0, 0.04, 1, 0.91))
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def generate_charts(agg: Sequence[Mapping], worker_specs, out_dir: Path, n_seeds: int,
                    detail_size: int | None = None) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    sizes = sorted({a["workload_size"] for a in agg})
    if not sizes:
        return []
    detail = detail_size if detail_size in sizes else sizes[-1]
    paths = [
        metric_chart(agg, "avg_waiting_time", "Average waiting time by algorithm", "Waiting time (simulated s)",
                     out_dir / "01_avg_waiting_time.png", n_seeds),
        metric_chart(agg, "avg_turnaround_time", "Average turnaround time by algorithm", "Turnaround time (simulated s)",
                     out_dir / "02_avg_turnaround_time.png", n_seeds),
        metric_chart(agg, "throughput", "Throughput by algorithm", "Tasks per simulated second",
                     out_dir / "03_throughput.png", n_seeds),
        metric_chart(agg, "avg_worker_utilisation_pct", "Mean simulated worker utilisation by algorithm",
                     "Simulated utilisation (%)", out_dir / "04_worker_utilisation.png", n_seeds),
        metric_chart(agg, "makespan", "Makespan by algorithm", "Makespan (simulated s)",
                     out_dir / "05_makespan.png", n_seeds),
        load_distribution_chart(agg, worker_specs, detail, out_dir / "06_load_distribution.png"),
        per_worker_utilisation_chart(agg, worker_specs, detail, out_dir / "07_per_worker_utilisation.png"),
        metric_chart(agg, "max_waiting_time", "Maximum waiting time by algorithm", "Maximum waiting time (simulated s)",
                     out_dir / "09_max_waiting_time.png", n_seeds),
        metric_chart(agg, "idle_while_waiting_pct", "Idle-while-waiting: free worker idle while a task waits elsewhere",
                     "% of available worker-time", out_dir / "10_idle_while_waiting.png", n_seeds),
    ]
    if {"fcfs_baseline", "shortest_job_first"} <= {a["algorithm"] for a in agg}:
        paths.append(fcfs_vs_sjf_chart(agg, detail, out_dir / "08_fcfs_vs_sjf.png", n_seeds))
    return sorted(paths)

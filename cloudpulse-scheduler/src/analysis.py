# Sample SD (n-1) across seeds. The FCFS control is aggregated but never ranked.
from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any, Iterable

from .schedulers import ALGORITHMS, PRIMARY

# key -> (label, unit, direction). direction: "lower" or "higher" is better.
METRICS: dict[str, tuple[str, str, str]] = {
    "avg_waiting_time": ("Average waiting time", "s", "lower"),
    "avg_turnaround_time": ("Average turnaround time", "s", "lower"),
    "avg_response_time": ("Average response time", "s", "lower"),
    "max_waiting_time": ("Maximum waiting time", "s", "lower"),
    "p95_waiting_time": ("95th-percentile waiting time", "s", "lower"),
    "makespan": ("Makespan", "s", "lower"),
    "throughput": ("Throughput", "tasks/s", "higher"),
    # Higher = workers busier. NOT automatically better: the same work takes longer
    # on a slow worker, so pushing work to slow workers also raises utilisation.
    "avg_worker_utilisation_pct": ("Mean worker utilisation", "%", "higher"),
    "utilisation_imbalance_cv": ("Utilisation imbalance (CV)", "", "lower"),
    "idle_while_waiting_pct": ("Idle-while-waiting", "% of worker-time", "lower"),
}

TYPE_METRICS = ("avg_waiting_time", "avg_turnaround_time", "max_waiting_time")


def _flat_value(row: dict, key: str) -> float:
    if key.startswith("by_type:"):
        _, task_type, metric = key.split(":")
        return row["by_task_type"][task_type][metric]
    return row[key]


def _mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    return statistics.fmean(values), statistics.stdev(values) if len(values) > 1 else 0.0


def group_key(row: dict) -> tuple[int, str]:
    return row["workload_size"], row["load_condition"]


def aggregate(rows: Iterable[dict]) -> list[dict[str, Any]]:
    rows = list(rows)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["workload_size"], r["load_condition"], r["algorithm"])].append(r)

    worker_ids = [p["worker_id"] for p in rows[0]["per_worker"]] if rows else []
    out = []
    for (size, load, algo), members in groups.items():
        entry: dict[str, Any] = {
            "workload_size": size,
            "load_condition": load,
            "target_utilisation": members[0]["target_utilisation"],
            "algorithm": algo,
            "role": members[0]["role"],
            "dispatch_mode": members[0]["dispatch_mode"],
            "n_seeds": len(members),
            "tasks_completed_min": min(m["tasks_completed"] for m in members),
            "tasks_completed_max": max(m["tasks_completed"] for m in members),
        }
        for key in METRICS:
            entry[f"{key}_mean"], entry[f"{key}_std"] = _mean_std([m[key] for m in members])
        for t in ("small", "medium", "large"):
            for mk in TYPE_METRICS:
                entry[f"{t}_{mk}_mean"], entry[f"{t}_{mk}_std"] = _mean_std(
                    [m["by_task_type"][t][mk] for m in members])
        for wid in worker_ids:
            for field in ("task_share_pct", "work_share_pct", "utilisation_pct"):
                vals = [next(p[field] for p in m["per_worker"] if p["worker_id"] == wid) for m in members]
                entry[f"{wid}_{field}_mean"], entry[f"{wid}_{field}_std"] = _mean_std(vals)
        out.append(entry)
    _attach_ranks(out, rows)
    return sorted(out, key=lambda e: (e["workload_size"], e["load_condition"], _algo_order(e["algorithm"])))


def _algo_order(name: str) -> int:
    order = list(ALGORITHMS) + ["fcfs_baseline"]
    return order.index(name) if name in order else len(order)


def _attach_ranks(agg: list[dict], rows: list[dict]) -> None:
    by_cell: dict[tuple, list[dict]] = defaultdict(list)
    for e in agg:
        if e["role"] == PRIMARY:
            by_cell[(e["workload_size"], e["load_condition"])].append(e)
    seed_rows: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        if r["role"] == PRIMARY:
            seed_rows[(r["workload_size"], r["load_condition"], r["seed"])].append(r)

    for key, (_, _, direction) in METRICS.items():
        sign = 1 if direction == "lower" else -1
        for cell, entries in by_cell.items():
            # competition ranking (1, 2, 2, 4) on means rounded to 9 dp
            scores = [round(sign * e[f"{key}_mean"], 9) for e in entries]
            for e, v in zip(entries, scores):
                e[f"{key}_rank"] = 1 + sum(1 for x in scores if x < v)
        wins: dict[tuple, int] = defaultdict(int)
        for (size, load, _seed), members in seed_rows.items():
            best = min(round(sign * m[key], 9) for m in members)
            for m in members:
                if round(sign * m[key], 9) == best:
                    wins[(size, load, m["algorithm"])] += 1
        for e in agg:
            if e["role"] == PRIMARY:
                e[f"{key}_wins"] = wins[(e["workload_size"], e["load_condition"], e["algorithm"])]


PAIRED_KEYS = (
    "avg_waiting_time",
    "avg_turnaround_time",
    "p95_waiting_time",
    "max_waiting_time",
    "makespan",
    "by_type:small:avg_waiting_time",
    "by_type:medium:avg_waiting_time",
    "by_type:large:avg_waiting_time",
    "by_type:large:max_waiting_time",
)


def fcfs_vs_sjf(rows: Iterable[dict]) -> list[dict[str, Any]]:
    # Paired per seed on identical workloads: delta = SJF - FCFS (negative = SJF lower).
    pairs: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        if r["algorithm"] in ("fcfs_baseline", "shortest_job_first"):
            pairs[(r["workload_size"], r["load_condition"], r["seed"])][r["algorithm"]] = r
    cells: dict[tuple, list[tuple[dict, dict]]] = defaultdict(list)
    for (size, load, seed), p in pairs.items():
        if len(p) == 2:
            if p["fcfs_baseline"]["workload_fingerprint"] != p["shortest_job_first"]["workload_fingerprint"]:
                raise RuntimeError(f"FCFS/SJF workload mismatch at size={size} load={load} seed={seed}")
            cells[(size, load)].append((p["fcfs_baseline"], p["shortest_job_first"]))

    out = []
    for (size, load), plist in sorted(cells.items()):
        for key in PAIRED_KEYS:
            fcfs_vals = [_flat_value(f, key) for f, _ in plist]
            sjf_vals = [_flat_value(s, key) for _, s in plist]
            deltas = [s - f for f, s in zip(fcfs_vals, sjf_vals)]
            f_mean, f_std = _mean_std(fcfs_vals)
            s_mean, s_std = _mean_std(sjf_vals)
            d_mean, d_std = _mean_std(deltas)
            out.append(
                {
                    "workload_size": size,
                    "load_condition": load,
                    "metric": key.replace("by_type:", "").replace(":", "_"),
                    "n_seeds": len(plist),
                    "fcfs_mean": f_mean,
                    "fcfs_std": f_std,
                    "sjf_mean": s_mean,
                    "sjf_std": s_std,
                    "delta_mean": d_mean,
                    "delta_std": d_std,
                    "pct_change": 100.0 * d_mean / f_mean if f_mean else 0.0,
                    "seeds_sjf_lower": sum(1 for d in deltas if d < -1e-9),
                    "seeds_sjf_higher": sum(1 for d in deltas if d > 1e-9),
                }
            )
    return out

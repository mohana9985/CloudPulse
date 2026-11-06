from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .analysis import METRICS
from .schedulers import DISPLAY_NAMES, PRIMARY
from .simulation_engine import SimulationResult
from .worker import WorkerSpec

_DP = 6


def _round(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, _DP) if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _round(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_round(v) for v in value]
    return value


def flatten_run(row: Mapping[str, Any]) -> dict[str, Any]:
    flat = {k: v for k, v in row.items() if k not in ("per_worker", "by_task_type")}
    for task_type, vals in row.get("by_task_type", {}).items():
        for k, v in vals.items():
            flat[f"{task_type}_{k}"] = v
    for p in row.get("per_worker", []):
        for k in ("tasks_completed", "busy_time", "utilisation_pct", "task_share_pct", "work_share_pct"):
            flat[f"{p['worker_id']}_{k}"] = p[k]
    return _round(flat)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    fields: list[str] = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _fmt(mean: float, std: float, n: int, dp: int = 2) -> str:
    return f"{mean:.{dp}f}" if n <= 1 else f"{mean:.{dp}f} ± {std:.{dp}f}"


def comparison_markdown(agg: Sequence[Mapping], fcfs: Sequence[Mapping], meta: Mapping) -> str:
    lines = [
        f"# Comparison tables — {meta['experiment_id']}",
        "",
        f"Generated {meta['timestamp']} from `algorithm_comparison.csv` / `fcfs_vs_sjf.csv`. "
        f"Values: mean ± sample SD across {meta['n_seeds']} seed(s). Times in simulated seconds. "
        "Rank (in brackets) is among the four primary algorithms only; FCFS is a control and is not ranked. "
        "Utilisation is simulated worker utilisation, not EC2 CPU.",
        "",
        "> **Reading utilisation:** a higher mean utilisation is *not* automatically better. The same work keeps a "
        "slow worker busy for longer, so a policy that overloads slow workers (e.g. RR) can show the highest "
        "utilisation together with the worst waiting times. Read it together with waiting time and the "
        "per-worker chart.",
        "",
    ]
    cols = [
        ("avg_waiting_time", 2), ("avg_turnaround_time", 2), ("p95_waiting_time", 2), ("max_waiting_time", 2),
        ("makespan", 1), ("throughput", 4), ("avg_worker_utilisation_pct", 1), ("idle_while_waiting_pct", 1),
    ]
    cells = sorted({(a["workload_size"], a["load_condition"], a["target_utilisation"]) for a in agg},
                   key=lambda c: (c[0], c[2]))
    for size, load, target in cells:
        lines += [f"## {size} tasks — {load} (target utilisation {target:.2f})", ""]
        header = ["Algorithm"] + [f"{METRICS[k][0]} ({METRICS[k][1]})" if METRICS[k][1] else METRICS[k][0] for k, _ in cols]
        lines += ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
        for a in (x for x in agg if x["workload_size"] == size and x["load_condition"] == load):
            cells_txt = [DISPLAY_NAMES.get(a["algorithm"], a["algorithm"])]
            for k, dp in cols:
                txt = _fmt(a[f"{k}_mean"], a[f"{k}_std"], a["n_seeds"], dp)
                if a["role"] == PRIMARY:
                    txt += f" [{a[f'{k}_rank']}]"
                cells_txt.append(txt)
            lines.append("| " + " | ".join(cells_txt) + " |")
        lines.append("")

    if fcfs:
        lines += ["## FCFS (control) vs SJF — same central queue, same worker choice", "",
                  "Δ = SJF − FCFS per seed on the identical workload; negative = SJF lower. "
                  "`SJF lower / higher` = number of seeds in each direction.", ""]
        lines += ["| Tasks | Load | Metric | FCFS | SJF | Δ mean ± SD | % change | SJF lower / higher |",
                  "|---|---|---|---|---|---|---|---|"]
        for f in fcfs:
            n = f["n_seeds"]
            lines.append(
                f"| {f['workload_size']} | {f['load_condition']} | {f['metric']} | {_fmt(f['fcfs_mean'], f['fcfs_std'], n)} | "
                f"{_fmt(f['sjf_mean'], f['sjf_std'], n)} | {_fmt(f['delta_mean'], f['delta_std'], n)} | "
                f"{f['pct_change']:+.1f}% | {f['seeds_sjf_lower']} / {f['seeds_sjf_higher']} |")
        lines.append("")
    return "\n".join(lines)


def best_per_metric(agg: Iterable[Mapping]) -> list[dict[str, Any]]:
    out = []
    for a in agg:
        if a["role"] != PRIMARY:
            continue
        for key in METRICS:
            if a[f"{key}_rank"] == 1:
                out.append({
                    "workload_size": a["workload_size"],
                    "load_condition": a["load_condition"],
                    "metric": key,
                    "direction": METRICS[key][2],
                    "best_algorithm": a["algorithm"],
                    "mean": a[f"{key}_mean"],
                    "seeds_won": a[f"{key}_wins"],
                    "n_seeds": a["n_seeds"],
                })
    return _round(out)


def write_experiment(
    out_dir: Path,
    meta: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    agg: Sequence[Mapping[str, Any]],
    fcfs: Sequence[Mapping[str, Any]],
    worker_specs: Sequence[WorkerSpec],
    single_results: Mapping[str, SimulationResult] | None = None,
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = {"experiment_id": meta["experiment_id"], "timestamp": meta["timestamp"]}
    files: dict[str, Path] = {}

    flat = [{**stamp, **flatten_run(r)} for r in rows]
    _write_csv(files.setdefault("results.csv", out_dir / "results.csv"), flat)

    nested = {**meta, "worker_config": [asdict(s) for s in worker_specs], "runs": [_round(dict(r)) for r in rows]}
    files["results.json"] = out_dir / "results.json"
    files["results.json"].write_text(json.dumps(nested, indent=2))

    files["algorithm_comparison.csv"] = out_dir / "algorithm_comparison.csv"
    _write_csv(files["algorithm_comparison.csv"], [{**stamp, **_round(dict(a))} for a in agg])

    if fcfs:
        files["fcfs_vs_sjf.csv"] = out_dir / "fcfs_vs_sjf.csv"
        _write_csv(files["fcfs_vs_sjf.csv"], [{**stamp, **_round(dict(f))} for f in fcfs])

    per_worker = []
    for r in rows:
        for p in r["per_worker"]:
            per_worker.append({**stamp, "workload_size": r["workload_size"], "load_condition": r["load_condition"],
                               "seed": r["seed"], "algorithm": r["algorithm"], "role": r["role"], **_round(p)})
    files["per_worker.csv"] = out_dir / "per_worker.csv"
    _write_csv(files["per_worker.csv"], per_worker)

    fingerprints = sorted({(r["workload_size"], r["load_condition"], r["seed"], r["workload_fingerprint"]) for r in rows})
    summary = {
        **meta,
        "worker_config": [asdict(s) for s in worker_specs],
        "worker_config_fingerprint": rows[0]["worker_config_fingerprint"] if rows else None,
        "workload_fingerprints": [
            {"workload_size": s, "load_condition": l, "seed": sd, "fingerprint": fp} for s, l, sd, fp in fingerprints
        ],
        "metric_definitions": {k: {"label": v[0], "unit": v[1], "better": v[2]} for k, v in METRICS.items()},
        "best_per_metric": best_per_metric(agg),
        "notes": [
            "FCFS (fcfs_baseline) is a control baseline, not a primary algorithm, and is excluded from rankings.",
            "All times are simulated seconds; throughput = tasks / simulated makespan.",
            "Utilisation is simulated worker busy time / makespan, not EC2 CPU or memory.",
        ],
    }
    files["experiment_summary.json"] = out_dir / "experiment_summary.json"
    files["experiment_summary.json"].write_text(json.dumps(_round(summary), indent=2))

    files["comparison_tables.md"] = out_dir / "comparison_tables.md"
    files["comparison_tables.md"].write_text(comparison_markdown(agg, fcfs, meta))

    if single_results:
        recs = []
        for name, res in single_results.items():
            for rec in res.records:
                recs.append({**stamp, "algorithm": name, **_round(asdict(rec)),
                             "waiting_time": round(rec.waiting_time, _DP),
                             "turnaround_time": round(rec.turnaround_time, _DP)})
        files["task_records.csv"] = out_dir / "task_records.csv"
        _write_csv(files["task_records.csv"], recs)
    return files

from __future__ import annotations

import argparse
import dataclasses
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .analysis import aggregate, fcfs_vs_sjf
from .config import DEFAULT_CONFIG_PATH, load_config, load_grid
from .experiment import GridSpec, run_comparison, run_grid
from .metrics import compute_metrics
from .results_exporter import write_experiment
from .schedulers import ALGORITHMS, ALL_CONFIGURATIONS, CONTROL_BASELINES, DISPLAY_NAMES
from .worker import WorkerSpec
from .workload_generator import generate_workload, load_workload, save_workload, workload_fingerprint

ROOT = Path(__file__).resolve().parent.parent


def _floats(text: str) -> list[float]:
    return [float(x) for x in text.split(",") if x.strip()]


def _ints(text: str) -> list[int]:
    return [int(x) for x in text.split(",") if x.strip()]


def _size_mix(text: str) -> dict[str, float]:
    out = {}
    for part in text.split(","):
        name, _, val = part.partition("=")
        if not val:
            raise argparse.ArgumentTypeError("size mix format: small=0.6,medium=0.3,large=0.1")
        out[name.strip()] = float(val)
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m src.main", description="CloudPulse workload scheduling simulator")
    choices = sorted(ALL_CONFIGURATIONS) + ["all"]
    p.add_argument("--algorithm", choices=choices, default="all",
                   help="primary algorithm, fcfs_baseline (control) or 'all' (4 primaries + FCFS control)")
    p.add_argument("--no-control", action="store_true", help="with --algorithm all: omit the FCFS control")
    p.add_argument("--grid", action="store_true", help="run the multi-seed/size/load grid from the config")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    p.add_argument("--tasks", type=int, help="number of tasks (default from config)")
    p.add_argument("--seed", type=int, help="random seed (default from config)")
    p.add_argument("--load", type=float, help="target utilisation, e.g. 0.5 / 0.85 / 1.2")
    p.add_argument("--workers", type=int, help="number of workers")
    p.add_argument("--capacities", type=_floats, help="comma list, e.g. 1.0,0.6,0.4")
    p.add_argument("--weights", type=_ints, help="WRR weights, comma list, e.g. 5,3,2")
    p.add_argument("--size-mix", type=_size_mix, help="e.g. small=0.6,medium=0.3,large=0.1")
    p.add_argument("--estimate-error", type=float, help="estimate noise fraction, e.g. 0.2")
    p.add_argument("--workload", type=Path, help="load a saved workload (.csv/.json) instead of generating")
    p.add_argument("--save-workload", type=Path, help="also save the workload used")
    p.add_argument("--generate-workload", type=Path, metavar="PATH", help="only generate + save a workload, then exit")
    p.add_argument("--seeds", type=_ints, help="grid override: comma list of seeds")
    p.add_argument("--sizes", type=_ints, help="grid override: comma list of task counts")
    p.add_argument("--results-dir", type=Path, default=ROOT / "results")
    p.add_argument("--charts-dir", type=Path, default=ROOT / "charts")
    p.add_argument("--experiment-id", help="output folder name (default: timestamped)")
    p.add_argument("--no-charts", action="store_true")
    return p


def resolve_workers(args, specs: list[WorkerSpec]) -> list[WorkerSpec]:
    n = args.workers or (len(args.capacities) if args.capacities else None) or len(specs)
    if n < 1:
        raise SystemExit("--workers must be >= 1")
    for name, lst in (("--capacities", args.capacities), ("--weights", args.weights)):
        if lst is not None and len(lst) != n:
            raise SystemExit(f"{name} needs exactly {n} values")
    out = []
    for i in range(n):
        base = specs[i] if i < len(specs) else WorkerSpec(f"W{i + 1}")
        out.append(dataclasses.replace(
            base,
            capacity=args.capacities[i] if args.capacities else base.capacity,
            weight=args.weights[i] if args.weights else base.weight,
        ))
    return out


def resolve_workload_config(args, base, specs):
    changes = {"total_capacity": sum(s.capacity for s in specs if s.available)}
    if args.tasks is not None:
        changes["num_tasks"] = args.tasks
    if args.seed is not None:
        changes["seed"] = args.seed
    if args.load is not None:
        changes["target_utilisation"] = args.load
    if args.size_mix is not None:
        changes["size_mix"] = args.size_mix
    if args.estimate_error is not None:
        changes["estimate_error"] = args.estimate_error
    return dataclasses.replace(base, **changes)


def _print_table(rows: list[dict]) -> None:
    head = f"{'Algorithm':16s} {'done':>5} {'avg wait':>9} {'avg TAT':>9} {'p95 wait':>9} {'max wait':>9} " \
           f"{'makespan':>9} {'thrpt':>7} {'util%':>6} {'idle-wait%':>10}"
    print(head)
    print("-" * len(head))
    for m in rows:
        print(f"{DISPLAY_NAMES.get(m['algorithm'], m['algorithm']):16s} {m['tasks_completed']:>5} "
              f"{m['avg_waiting_time']:>9.2f} {m['avg_turnaround_time']:>9.2f} {m['p95_waiting_time']:>9.2f} "
              f"{m['max_waiting_time']:>9.2f} {m['makespan']:>9.1f} {m['throughput']:>7.4f} "
              f"{m['avg_worker_utilisation_pct']:>6.1f} {m['idle_while_waiting_pct']:>10.1f}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        base_cfg, config_specs = load_config(args.config)
        specs = resolve_workers(args, config_specs)
        wl_cfg = resolve_workload_config(args, base_cfg, specs)
    except (ValueError, KeyError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    if args.generate_workload:
        tasks = generate_workload(wl_cfg)
        save_workload(tasks, args.generate_workload, metadata=dataclasses.asdict(wl_cfg))
        print(f"Saved {len(tasks)} tasks (seed {wl_cfg.seed}, fingerprint {workload_fingerprint(tasks)[:12]}) "
              f"-> {args.generate_workload}")
        return 0

    now = datetime.now(timezone.utc)
    timestamp = now.isoformat(timespec="seconds")
    mode = "grid" if args.grid else "single"
    exp_id = args.experiment_id or f"{mode}-{now.strftime('%Y%m%dT%H%M%SZ')}"
    t0 = time.perf_counter()

    if args.grid:
        grid = load_grid(args.config)
        grid = GridSpec(sizes=tuple(args.sizes) if args.sizes else grid.sizes,
                        seeds=tuple(args.seeds) if args.seeds else grid.seeds, loads=grid.loads)
        algos = list(ALGORITHMS) if args.no_control else list(ALL_CONFIGURATIONS)
        rows = run_grid(wl_cfg, specs, grid, algos)
        single = None
        meta = {"experiment_id": exp_id, "timestamp": timestamp, "mode": "grid",
                "workload_sizes": list(grid.sizes), "seeds": list(grid.seeds),
                "load_conditions": dict(grid.loads), "n_seeds": len(grid.seeds)}
    else:
        if args.workload:
            tasks = load_workload(args.workload)
            source = str(args.workload)
        else:
            tasks = generate_workload(wl_cfg)
            source = "generated"
        if args.save_workload:
            save_workload(tasks, args.save_workload, metadata=dataclasses.asdict(wl_cfg))
        if args.algorithm == "all":
            algos = list(ALGORITHMS) + ([] if args.no_control else list(CONTROL_BASELINES))
        else:
            algos = [args.algorithm]
        single = run_comparison(tasks, specs, algos)
        load_label = "loaded_file" if args.workload else f"rho_{wl_cfg.target_utilisation:g}"
        rows = [{"workload_size": len(tasks), "load_condition": load_label,
                 "target_utilisation": wl_cfg.target_utilisation if not args.workload else float("nan"),
                 "seed": wl_cfg.seed if not args.workload else None, **compute_metrics(r)} for r in single.values()]
        meta = {"experiment_id": exp_id, "timestamp": timestamp, "mode": "single", "workload_source": source,
                "workload_sizes": [len(tasks)], "seeds": [wl_cfg.seed] if not args.workload else [],
                "target_utilisation": wl_cfg.target_utilisation, "n_seeds": 1,
                "workload_fingerprint": workload_fingerprint(tasks)}

    meta["workload_generator"] = {k: v for k, v in dataclasses.asdict(wl_cfg).items() if k not in ("num_tasks", "seed")}
    meta["sim_wall_clock_seconds"] = round(time.perf_counter() - t0, 3)  # informational only, never a metric
    agg = aggregate(rows)
    fcfs = fcfs_vs_sjf(rows)
    files = write_experiment(args.results_dir / exp_id, meta, rows, agg, fcfs, specs, single)
    charts = [] if args.no_charts else __import__("src.charts", fromlist=["generate_charts"]).generate_charts(
        agg, specs, args.charts_dir / exp_id, meta["n_seeds"])

    print(f"CloudPulse Scheduler — experiment {exp_id} ({mode})")
    print("Workers: " + ", ".join(f"{s.worker_id}(cap {s.capacity:g}, w {s.weight})" for s in specs))
    if args.grid:
        print(f"Grid: sizes {list(grid.sizes)} × loads {dict(grid.loads)} × {len(grid.seeds)} seeds × "
              f"{len(algos)} configurations = {len(rows)} runs")
        largest = max(grid.sizes)
        for load_name, _ in grid.loads:
            print(f"\nMean across seeds — {largest} tasks, {load_name} ('done' = minimum over seeds):")
            _print_table([{**{k: a[f'{k}_mean'] for k in ('avg_waiting_time', 'avg_turnaround_time', 'p95_waiting_time',
                                                          'max_waiting_time', 'makespan', 'throughput',
                                                          'avg_worker_utilisation_pct', 'idle_while_waiting_pct')},
                            "algorithm": a["algorithm"], "tasks_completed": a["tasks_completed_min"]}
                          for a in agg if a["workload_size"] == largest and a["load_condition"] == load_name])
    else:
        print(f"Workload: {len(tasks)} tasks, seed {meta['seeds'] or '-'}, source {source}, "
              f"fingerprint {meta['workload_fingerprint'][:12]}")
        print()
        _print_table(rows)
    print("\nTimes in simulated seconds. Utilisation = simulated workers, not EC2 CPU. FCFS = control baseline.")
    print(f"Results: {args.results_dir / exp_id}  ({', '.join(sorted(files))})")
    if charts:
        print(f"Charts:  {args.charts_dir / exp_id}  ({len(charts)} PNG files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

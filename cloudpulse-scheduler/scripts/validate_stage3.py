from __future__ import annotations

import dataclasses
import hashlib
import json

from src.config import load_config
from src.experiment import run_comparison
from src.metrics import compute_metrics
from src.schedulers import ALGORITHMS, create_scheduler
from src.simulation_engine import run_simulation
from src.worker import WorkerSpec
from src.workload_generator import generate_workload, workload_fingerprint
from tests.invariants import check_schedule, reference_metrics

ALGOS = list(ALGORITHMS)
SIZES = (100, 250, 500)


def digest(result) -> str:
    return hashlib.sha256(json.dumps([dataclasses.astuple(r) for r in result.records]).encode()).hexdigest()[:12]


def main() -> None:
    base_cfg, specs = load_config()
    print("Workers:", [(s.worker_id, s.capacity, s.weight) for s in specs])
    print(f"Seed={base_cfg.seed} target_utilisation={base_cfg.target_utilisation} estimate_error={base_cfg.estimate_error}\n")

    print("== 1. Identical inputs (fingerprint seen by each engine run) ==")
    for n in SIZES:
        tasks = generate_workload(dataclasses.replace(base_cfg, num_tasks=n))
        res = run_comparison(tasks, specs)
        wl = {r.workload_fingerprint[:12] for r in res.values()}
        wk = {r.worker_config_fingerprint[:12] for r in res.values()}
        print(f"n={n}: workload fp per algo -> {sorted(wl)} | worker fp -> {sorted(wk)} | "
              f"expected {workload_fingerprint(tasks)[:12]}")

    print("\n== 2. Determinism (10 repeats, n=250) ==")
    tasks = generate_workload(dataclasses.replace(base_cfg, num_tasks=250))
    for a in ALGOS:
        ds = {digest(run_simulation(tasks, specs, create_scheduler(a))) for _ in range(10)}
        print(f"{a:22s} distinct result digests: {len(ds)}  ({next(iter(ds))})")

    print("\n== 3-6. Integrity + independent metric check ==")
    print(f"{'n':>4} {'algorithm':22s} {'done':>5} {'violations':>10} {'max|metric-ref|':>16}")
    for n in SIZES:
        tasks = generate_workload(dataclasses.replace(base_cfg, num_tasks=n))
        for a, r in run_comparison(tasks, specs).items():
            v = check_schedule(r, tasks, specs)
            m, ref = compute_metrics(r), reference_metrics(r, specs)
            diff = max(abs(m[k] - ref[k]) for k in ref)
            print(f"{n:>4} {a:22s} {len(r.records):>5} {len(v):>10} {diff:>16.2e}")

    print("\n== 7. Hybrid-design diagnostic: idle-while-waiting (worker-seconds) ==")
    for n in SIZES:
        tasks = generate_workload(dataclasses.replace(base_cfg, num_tasks=n))
        res = run_comparison(tasks, specs)
        print(f"n={n}: " + "  ".join(f"{a}={r.idle_while_waiting_time:.1f} ({100*r.idle_while_waiting_time/(r.makespan*len(specs)):.1f}% of capacity-time)"
                                       for a, r in res.items()))

    print("\n== 9. Edge cases ==")
    empty = run_comparison([], specs)
    print("empty workload:", {a: (len(r.records), r.makespan) for a, r in empty.items()})
    un_specs = [specs[0], dataclasses.replace(specs[1], available=False), specs[2]]
    tasks = generate_workload(dataclasses.replace(base_cfg, num_tasks=250, total_capacity=1.4))
    un = run_comparison(tasks, un_specs)
    print("W2 unavailable (n=250):", {a: [w.tasks_completed for w in r.workers] for a, r in un.items()},
          "violations:", sum(len(check_schedule(r, tasks, un_specs)) for r in un.values()))
    burst = [dataclasses.replace(t, arrival_time=10.0) for t in generate_workload(dataclasses.replace(base_cfg, num_tasks=100))]
    br = run_comparison(burst, specs)
    print("100 simultaneous arrivals at t=10:", {a: len(r.records) for a, r in br.items()},
          "violations:", sum(len(check_schedule(r, burst, specs)) for r in br.values()))
    over = generate_workload(dataclasses.replace(base_cfg, num_tasks=500, target_utilisation=1.5))
    ov = run_comparison(over, specs)
    print("overload 150% (n=500):", {a: (len(r.records), r.peak_queue_length) for a, r in ov.items()},
          "violations:", sum(len(check_schedule(r, over, specs)) for r in ov.values()))
    lim = [dataclasses.replace(s, max_queue_length=2) for s in specs]
    ol = run_comparison(over, lim)
    print("overload + max_queue_length=2:", {a: len(r.records) for a, r in ol.items()},
          "violations:", sum(len(check_schedule(r, over, lim)) for r in ol.values()))


if __name__ == "__main__":
    main()

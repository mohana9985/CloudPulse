# All times are simulated seconds; utilisation is simulated busy time, not EC2 CPU.
from __future__ import annotations

import math
import statistics
from typing import Any

from .simulation_engine import SimulationResult


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _ratio(num: float, den: float) -> float:
    return num / den if den > 0 else 0.0


def percentile(values: list[float], pct: float) -> float:
    # Nearest-rank percentile, no interpolation.
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


TASK_TYPES = ("small", "medium", "large")


def compute_metrics(result: SimulationResult) -> dict[str, Any]:
    records = result.records
    makespan = result.makespan
    waits = [r.waiting_time for r in records]
    total_tasks = len(records)
    total_work = sum(r.actual_duration for r in records)
    total_busy = sum(w.busy_time for w in result.workers)

    per_worker = []
    for w in result.workers:
        per_worker.append(
            {
                "worker_id": w.worker_id,
                "capacity": w.capacity,
                "weight": w.weight,
                "available": w.available,
                "tasks_completed": w.tasks_completed,
                "busy_time": w.busy_time,
                "utilisation_pct": 100.0 * w.utilisation(makespan),
                "task_share_pct": 100.0 * _ratio(w.tasks_completed, total_tasks),
                "work_share_pct": 100.0 * _ratio(w.completed_actual_work, total_work),
                "busy_share_pct": 100.0 * _ratio(w.busy_time, total_busy),
            }
        )

    by_type: dict[str, dict[str, float]] = {}
    for task_type in TASK_TYPES:
        subset = [r for r in records if r.task_type == task_type]
        by_type[task_type] = {
            "count": len(subset),
            "avg_waiting_time": _mean([r.waiting_time for r in subset]),
            "avg_turnaround_time": _mean([r.turnaround_time for r in subset]),
            "max_waiting_time": max((r.waiting_time for r in subset), default=0.0),
        }

    n_available = sum(1 for w in result.workers if w.available)
    available_utils = [p["utilisation_pct"] for p in per_worker if p["available"]]
    mean_util = _mean(available_utils)
    imbalance = statistics.pstdev(available_utils) / mean_util if len(available_utils) > 1 and mean_util > 0 else 0.0

    return {
        "algorithm": result.algorithm,
        "role": result.role,
        "dispatch_mode": result.dispatch_mode,
        "tasks_completed": total_tasks,
        "avg_waiting_time": _mean(waits),
        "avg_turnaround_time": _mean([r.turnaround_time for r in records]),
        "avg_response_time": _mean([r.response_time for r in records]),
        "max_waiting_time": max(waits, default=0.0),
        "p95_waiting_time": percentile(waits, 95),
        "makespan": makespan,
        "throughput": _ratio(total_tasks, makespan),
        "avg_worker_utilisation_pct": mean_util,
        "utilisation_imbalance_cv": imbalance,  # 0 = perfectly even utilisation
        "peak_queue_length": result.peak_queue_length,
        "avg_queue_length": result.avg_queue_length,
        "idle_while_waiting_time": result.idle_while_waiting_time,
        # % of available worker-time spent idle while a task waited elsewhere
        "idle_while_waiting_pct": 100.0 * _ratio(result.idle_while_waiting_time, makespan * n_available),
        "workload_fingerprint": result.workload_fingerprint,
        "worker_config_fingerprint": result.worker_config_fingerprint,
        "by_task_type": by_type,
        "per_worker": per_worker,
    }

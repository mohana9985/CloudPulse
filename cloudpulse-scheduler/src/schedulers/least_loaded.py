# load(w) = est. remaining time of running task + queued estimates, both / capacity.
from __future__ import annotations

from typing import Sequence

from ..worker import Worker
from ..workload_generator import Task
from .base import PerWorkerQueueScheduler

_TIE_DECIMALS = 9  # absorb float noise so equal loads are treated as ties


class LeastLoadedScheduler(PerWorkerQueueScheduler):
    name = "least_loaded"

    def select_worker(self, task: Task, workers: Sequence[Worker], now: float) -> Worker | None:
        eligible = [w for w in workers if w.can_accept()]
        if not eligible:
            return None
        loads = {w.worker_id: w.estimated_load(now) for w in eligible}
        best = min(eligible, key=lambda w: (round(loads[w.worker_id], _TIE_DECIMALS), self._order(w)))
        load_after = loads[best.worker_id] + best.estimated_execution_time(task)
        self.decision_log.append(
            {
                "time": now,
                "task_id": task.task_id,
                "worker_id": best.worker_id,
                "loads_before": loads,
                "load_after": load_after,
            }
        )
        return best

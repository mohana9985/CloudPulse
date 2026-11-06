# Smooth (Nginx-style) WRR: picks are interleaved, not sent in bursts.
from __future__ import annotations

from typing import Mapping, Sequence

from ..worker import Worker, validate_weight
from ..workload_generator import Task
from .base import PerWorkerQueueScheduler


class WeightedRoundRobinScheduler(PerWorkerQueueScheduler):
    name = "weighted_round_robin"

    def __init__(self, weights: Mapping[str, int] | None = None) -> None:
        super().__init__()
        self._override = dict(weights) if weights else {}

    def reset(self, workers: Sequence[Worker]) -> None:
        super().reset(workers)
        ids = {w.worker_id for w in workers}
        unknown = set(self._override) - ids
        if unknown:
            raise ValueError(f"Weights given for unknown workers: {sorted(unknown)}")
        self._weights = {
            w.worker_id: validate_weight(self._override.get(w.worker_id, w.weight), w.worker_id) for w in workers
        }
        self._current = {w.worker_id: 0 for w in workers}

    def weight_of(self, worker: Worker) -> int:
        return self._weights[worker.worker_id]

    def select_worker(self, task: Task, workers: Sequence[Worker], now: float) -> Worker | None:
        eligible = [w for w in workers if w.can_accept()]
        if not eligible:
            return None
        total = sum(self._weights[w.worker_id] for w in eligible)
        best: Worker | None = None
        for w in eligible:  # config order, strict '>' keeps lowest index on ties
            self._current[w.worker_id] += self._weights[w.worker_id]
            if best is None or self._current[w.worker_id] > self._current[best.worker_id]:
                best = w
        assert best is not None
        self._current[best.worker_id] -= total
        self.decision_log.append({"time": now, "task_id": task.task_id, "worker_id": best.worker_id})
        return best

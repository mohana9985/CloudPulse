from __future__ import annotations

from typing import Sequence

from ..worker import Worker
from ..workload_generator import Task
from .base import PerWorkerQueueScheduler


class RoundRobinScheduler(PerWorkerQueueScheduler):
    name = "round_robin"

    def reset(self, workers: Sequence[Worker]) -> None:
        super().reset(workers)
        self._pointer = 0

    def select_worker(self, task: Task, workers: Sequence[Worker], now: float) -> Worker | None:
        n = len(workers)
        for offset in range(n):
            idx = (self._pointer + offset) % n
            worker = workers[idx]
            if worker.can_accept():
                self._pointer = (idx + 1) % n
                self.decision_log.append(
                    {"time": now, "task_id": task.task_id, "worker_id": worker.worker_id, "skipped": offset}
                )
                return worker
        return None

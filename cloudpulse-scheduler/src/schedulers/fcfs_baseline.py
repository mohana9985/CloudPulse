# FCFS control baseline, not a primary algorithm: same central queue and worker
# selection as SJF, ordered by (arrival_time, task_id). SJF - FCFS = effect of ordering.
from __future__ import annotations

from collections import deque
from typing import Sequence

from ..worker import Worker
from ..workload_generator import Task
from .base import CONTROL, CentralQueueScheduler


class FCFSBaselineScheduler(CentralQueueScheduler):
    name = "fcfs_baseline"
    role = CONTROL

    def reset(self, workers: Sequence[Worker]) -> None:
        super().reset(workers)
        self._ready: deque[Task] = deque()

    def add_task(self, task: Task) -> None:
        # Engine delivers arrivals in (arrival_time, task_id) order, so append keeps FCFS order.
        self._ready.append(task)

    def pending_count(self) -> int:
        return len(self._ready)

    def pop_next_task(self, now: float, worker: Worker) -> Task:
        queue_len = len(self._ready)
        task = self._ready.popleft()
        self.decision_log.append(
            {"time": now, "task_id": task.task_id, "worker_id": worker.worker_id, "queue_length_before": queue_len}
        )
        return task

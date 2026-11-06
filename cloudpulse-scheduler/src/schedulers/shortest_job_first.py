# Non-preemptive: a started task always runs to completion.
from __future__ import annotations

import heapq
from typing import Sequence

from ..worker import Worker
from ..workload_generator import Task
from .base import CentralQueueScheduler


class ShortestJobFirstScheduler(CentralQueueScheduler):
    name = "shortest_job_first"

    def reset(self, workers: Sequence[Worker]) -> None:
        super().reset(workers)
        self._ready: list[tuple[float, float, int, Task]] = []

    def add_task(self, task: Task) -> None:
        # task_id is unique, so the Task object itself is never compared.
        heapq.heappush(self._ready, (task.estimated_duration, task.arrival_time, task.task_id, task))

    def pending_count(self) -> int:
        return len(self._ready)

    def pop_next_task(self, now: float, worker: Worker) -> Task:
        queue_len = len(self._ready)
        task = heapq.heappop(self._ready)[3]
        self.decision_log.append(
            {"time": now, "task_id": task.task_id, "worker_id": worker.worker_id, "queue_length_before": queue_len}
        )
        return task

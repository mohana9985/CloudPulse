from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Sequence

from ..worker import Worker
from ..workload_generator import Task

PER_WORKER_QUEUE = "per_worker_queue"
CENTRAL_QUEUE = "central_queue"
PRIMARY = "primary"
CONTROL = "control"   # baseline used only to interpret the primary results


class Scheduler(ABC):
    name: ClassVar[str]
    dispatch_mode: ClassVar[str]
    role: ClassVar[str] = PRIMARY

    def __init__(self) -> None:
        self.decision_log: list[dict[str, Any]] = []

    def reset(self, workers: Sequence[Worker]) -> None:
        self.decision_log = []
        self._index = {w.worker_id: i for i, w in enumerate(workers)}

    def _order(self, worker: Worker) -> int:
        return self._index[worker.worker_id]


class PerWorkerQueueScheduler(Scheduler):
    dispatch_mode = PER_WORKER_QUEUE

    @abstractmethod
    def select_worker(self, task: Task, workers: Sequence[Worker], now: float) -> Worker | None: ...


class CentralQueueScheduler(Scheduler):
    dispatch_mode = CENTRAL_QUEUE

    @abstractmethod
    def add_task(self, task: Task) -> None: ...

    @abstractmethod
    def pending_count(self) -> int: ...

    @abstractmethod
    def pop_next_task(self, now: float, worker: Worker) -> Task: ...

    def select_idle_worker(self, idle_workers: Sequence[Worker]) -> Worker:
        # Shared by SJF and the FCFS control so they differ only in task ordering.
        if not idle_workers:
            raise ValueError("select_idle_worker called with no idle workers")
        return min(idle_workers, key=lambda w: (-w.capacity, self._order(w)))

    def has_pending(self) -> bool:
        return self.pending_count() > 0

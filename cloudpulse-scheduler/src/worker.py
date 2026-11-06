from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from dataclasses import asdict, dataclass
from typing import Iterable

from .workload_generator import Task


@dataclass(frozen=True)
class WorkerSpec:
    worker_id: str
    capacity: float = 1.0
    weight: int = 1
    available: bool = True
    # Max tasks a worker may hold at once (running + queued). None = unlimited.
    max_queue_length: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.worker_id, str) or not self.worker_id:
            raise ValueError("worker_id must be a non-empty string")
        if (
            not isinstance(self.capacity, (int, float))
            or isinstance(self.capacity, bool)
            or not math.isfinite(self.capacity)
            or self.capacity <= 0
        ):
            raise ValueError(f"Worker {self.worker_id}: capacity must be a finite number > 0")
        validate_weight(self.weight, self.worker_id)
        if not isinstance(self.available, bool):
            raise ValueError(f"Worker {self.worker_id}: available must be true/false")
        if self.max_queue_length is not None and (
            not isinstance(self.max_queue_length, int)
            or isinstance(self.max_queue_length, bool)
            or self.max_queue_length < 1
        ):
            raise ValueError(f"Worker {self.worker_id}: max_queue_length must be an integer >= 1 or null")


def specs_fingerprint(specs: Iterable[WorkerSpec]) -> str:
    return hashlib.sha256(json.dumps([asdict(s) for s in specs], sort_keys=True).encode()).hexdigest()


def validate_weight(weight: object, worker_id: str) -> int:
    if not isinstance(weight, int) or isinstance(weight, bool) or weight < 1:
        raise ValueError(f"Worker {worker_id}: weight must be an integer >= 1, got {weight!r}")
    return weight


class Worker:
    def __init__(self, spec: WorkerSpec) -> None:
        self.spec = spec
        self.worker_id = spec.worker_id
        self.capacity = float(spec.capacity)
        self.weight = spec.weight
        self.available = spec.available
        self.max_queue_length = spec.max_queue_length

        self.queue: deque[Task] = deque()
        self.current_task: Task | None = None
        self.current_start: float | None = None
        self.current_end: float | None = None

        self.busy_time = 0.0
        self.tasks_completed = 0
        self.tasks_assigned = 0
        self.assigned_estimated_work = 0.0
        self.completed_actual_work = 0.0
        self.completed_task_ids: list[int] = []

    @property
    def is_idle(self) -> bool:
        return self.current_task is None

    @property
    def status(self) -> str:
        if not self.available:
            return "unavailable"
        return "idle" if self.is_idle else "busy"

    @property
    def outstanding(self) -> int:
        return len(self.queue) + (0 if self.current_task is None else 1)

    @property
    def total_execution_time(self) -> float:
        return self.busy_time

    def can_accept(self) -> bool:
        if not self.available:
            return False
        return self.max_queue_length is None or self.outstanding < self.max_queue_length

    def execution_time(self, task: Task) -> float:
        return task.actual_duration / self.capacity

    def estimated_execution_time(self, task: Task) -> float:
        return task.estimated_duration / self.capacity

    def estimated_load(self, now: float) -> float:
        load = 0.0
        if self.current_task is not None and self.current_start is not None:
            expected_end = self.current_start + self.estimated_execution_time(self.current_task)
            load += max(0.0, expected_end - now)
        load += sum(self.estimated_execution_time(t) for t in self.queue)
        return load

    def record_assignment(self, task: Task) -> None:
        self.tasks_assigned += 1
        self.assigned_estimated_work += task.estimated_duration

    def enqueue(self, task: Task) -> None:
        if not self.can_accept():
            raise RuntimeError(f"Worker {self.worker_id} cannot accept task {task.task_id}")
        self.queue.append(task)
        self.record_assignment(task)

    def start(self, task: Task, now: float) -> float:
        if not self.available:
            raise RuntimeError(f"Worker {self.worker_id} is unavailable")
        if self.current_task is not None:
            raise RuntimeError(f"Worker {self.worker_id} is already running task {self.current_task.task_id}")
        self.current_task = task
        self.current_start = now
        self.current_end = now + self.execution_time(task)
        return self.current_end

    def complete(self, now: float) -> tuple[Task, float]:
        if self.current_task is None or self.current_start is None:
            raise RuntimeError(f"Worker {self.worker_id} has no running task to complete")
        task, start = self.current_task, self.current_start
        self.busy_time += now - start
        self.tasks_completed += 1
        self.completed_actual_work += task.actual_duration
        self.completed_task_ids.append(task.task_id)
        self.current_task = self.current_start = self.current_end = None
        return task, start

    def utilisation(self, makespan: float) -> float:
        return self.busy_time / makespan if makespan > 0 else 0.0

    def __repr__(self) -> str:
        return f"Worker({self.worker_id}, cap={self.capacity}, w={self.weight}, {self.status}, q={len(self.queue)})"

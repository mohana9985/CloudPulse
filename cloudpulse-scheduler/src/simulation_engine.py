# Same-time events: COMPLETION before ARRIVAL; all events at one timestamp are
# applied before a single dispatch step.
from __future__ import annotations

import heapq
import itertools
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from .schedulers.base import CentralQueueScheduler, PerWorkerQueueScheduler, Scheduler
from .worker import Worker, WorkerSpec, specs_fingerprint
from .workload_generator import Task, validate_workload, workload_fingerprint

_COMPLETION = 0
_ARRIVAL = 1


@dataclass(frozen=True)
class TaskRecord:
    task_id: int
    task_type: str
    worker_id: str
    arrival_time: float
    start_time: float
    completion_time: float
    estimated_duration: float
    actual_duration: float
    execution_time: float

    @property
    def waiting_time(self) -> float:
        return self.start_time - self.arrival_time

    @property
    def response_time(self) -> float:
        # Non-preemptive: first execution == only execution, so equals waiting time.
        return self.start_time - self.arrival_time

    @property
    def turnaround_time(self) -> float:
        return self.completion_time - self.arrival_time


@dataclass
class SimulationResult:
    algorithm: str
    dispatch_mode: str
    role: str
    records: list[TaskRecord]
    workers: list[Worker]
    makespan: float
    decision_log: list[dict[str, Any]] = field(default_factory=list)
    peak_queue_length: int = 0
    avg_queue_length: float = 0.0
    # Worker-seconds in which an available worker sat idle while some task was
    # waiting elsewhere. Always 0 for the central queue (SJF); can be > 0 for
    # per-worker queues because queued tasks are never moved (no work stealing).
    idle_while_waiting_time: float = 0.0
    workload_fingerprint: str = ""
    worker_config_fingerprint: str = ""


def validate_worker_specs(specs: Iterable[WorkerSpec]) -> list[WorkerSpec]:
    spec_list = list(specs)
    if not spec_list:
        raise ValueError("At least one worker is required")
    ids = [s.worker_id for s in spec_list]
    if len(set(ids)) != len(ids):
        raise ValueError(f"Duplicate worker_id in {ids}")
    if not any(s.available for s in spec_list):
        raise ValueError("At least one worker must be available")
    return spec_list


class SimulationEngine:
    def __init__(self, worker_specs: Sequence[WorkerSpec], scheduler: Scheduler) -> None:
        if not isinstance(scheduler, (PerWorkerQueueScheduler, CentralQueueScheduler)):
            raise TypeError("scheduler must be a PerWorkerQueueScheduler or CentralQueueScheduler")
        self.worker_specs = validate_worker_specs(worker_specs)
        self.scheduler = scheduler

    def run(self, tasks: Iterable[Task]) -> SimulationResult:
        task_list = validate_workload(tasks)
        self.workers = [Worker(s) for s in self.worker_specs]
        self.scheduler.reset(self.workers)

        self._heap: list[tuple[float, int, int, Any]] = []
        self._seq = itertools.count()
        self._backlog: deque[Task] = deque()
        self._started: set[int] = set()
        self._records: dict[int, TaskRecord] = {}

        for task in sorted(task_list, key=lambda t: (t.arrival_time, t.task_id)):
            heapq.heappush(self._heap, (task.arrival_time, _ARRIVAL, next(self._seq), task))

        peak_q, q_area, last_t, last_q = 0, 0.0, 0.0, 0
        iww_time, last_idle_waiting = 0.0, 0
        while self._heap:
            now = self._heap[0][0]
            q_area += last_q * (now - last_t)
            iww_time += last_idle_waiting * (now - last_t)
            while self._heap and self._heap[0][0] == now:
                _, kind, _, payload = heapq.heappop(self._heap)
                if kind == _COMPLETION:
                    self._on_completion(payload, now)
                else:
                    self._on_arrival(payload, now)
            self._dispatch(now)
            last_t, last_q = now, self._pending_count()
            peak_q = max(peak_q, last_q)
            idle_available = sum(1 for w in self.workers if w.available and w.is_idle)
            last_idle_waiting = idle_available if last_q > 0 else 0

        self._verify(task_list)
        records = sorted(self._records.values(), key=lambda r: r.task_id)
        makespan = max((r.completion_time for r in records), default=0.0)
        return SimulationResult(
            algorithm=self.scheduler.name,
            dispatch_mode=self.scheduler.dispatch_mode,
            role=self.scheduler.role,
            records=records,
            workers=self.workers,
            makespan=makespan,
            decision_log=list(self.scheduler.decision_log),
            peak_queue_length=peak_q,
            avg_queue_length=q_area / makespan if makespan > 0 else 0.0,
            idle_while_waiting_time=iww_time,
            workload_fingerprint=workload_fingerprint(task_list),
            worker_config_fingerprint=specs_fingerprint(self.worker_specs),
        )

    def _pending_count(self) -> int:
        n = len(self._backlog) + sum(len(w.queue) for w in self.workers)
        if isinstance(self.scheduler, CentralQueueScheduler):
            n += self.scheduler.pending_count()
        return n

    def _on_arrival(self, task: Task, now: float) -> None:
        sched = self.scheduler
        if isinstance(sched, CentralQueueScheduler):
            sched.add_task(task)
            return
        if self._backlog:  # keep FIFO order behind tasks already waiting
            self._backlog.append(task)
            return
        worker = sched.select_worker(task, self.workers, now)
        if worker is None:
            self._backlog.append(task)
        else:
            worker.enqueue(task)

    def _on_completion(self, worker: Worker, now: float) -> None:
        task, start = worker.complete(now)
        if task.task_id in self._records:
            raise RuntimeError(f"Task {task.task_id} completed twice")
        self._records[task.task_id] = TaskRecord(
            task_id=task.task_id,
            task_type=task.task_type,
            worker_id=worker.worker_id,
            arrival_time=task.arrival_time,
            start_time=start,
            completion_time=now,
            estimated_duration=task.estimated_duration,
            actual_duration=task.actual_duration,
            execution_time=now - start,
        )

    def _start(self, worker: Worker, task: Task, now: float) -> None:
        if task.task_id in self._started:
            raise RuntimeError(f"Task {task.task_id} started twice")
        self._started.add(task.task_id)
        end = worker.start(task, now)
        heapq.heappush(self._heap, (end, _COMPLETION, next(self._seq), worker))

    def _dispatch(self, now: float) -> None:
        sched = self.scheduler
        if isinstance(sched, CentralQueueScheduler):
            idle = [w for w in self.workers if w.available and w.is_idle]
            while idle and sched.has_pending():
                worker = sched.select_idle_worker(idle)
                idle.remove(worker)
                task = sched.pop_next_task(now, worker)
                worker.record_assignment(task)
                self._start(worker, task, now)
            return

        while self._backlog:
            worker = sched.select_worker(self._backlog[0], self.workers, now)
            if worker is None:
                break
            worker.enqueue(self._backlog.popleft())
        for worker in self.workers:
            if worker.available and worker.is_idle and worker.queue:
                self._start(worker, worker.queue.popleft(), now)

    def _verify(self, task_list: list[Task]) -> None:
        expected = {t.task_id for t in task_list}
        if self._pending_count() or any(not w.is_idle for w in self.workers):
            raise RuntimeError("Simulation ended with unfinished tasks (no worker could accept them)")
        if set(self._records) != expected or len(self._records) != len(task_list):
            missing = expected - set(self._records)
            raise RuntimeError(f"Task accounting mismatch; missing={sorted(missing)[:10]}")


def run_simulation(tasks: Iterable[Task], worker_specs: Sequence[WorkerSpec], scheduler: Scheduler) -> SimulationResult:
    return SimulationEngine(worker_specs, scheduler).run(tasks)

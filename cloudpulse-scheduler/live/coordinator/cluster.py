# Scheduling decisions are made by the SAME classes used by the offline simulator
# (src/schedulers). Each real worker has a "mirror" src.worker.Worker object that holds
# its per-worker queue and current task, so RR/WRR/LL call select_worker() and SJF/FCFS
# call pop_next_task()/select_idle_worker() exactly as in SimulationEngine.
# Workers PULL work: they long-poll /workers/{id}/poll. A task is "delivered" when an idle,
# active worker is waiting. Availability comes only from heartbeats (no static flag).
# All mutation happens on the asyncio event loop thread, so no locks are needed.

from __future__ import annotations

import asyncio
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

from src.schedulers import (
    ALL_CONFIGURATIONS,
    CentralQueueScheduler,
    PerWorkerQueueScheduler,
    WeightedRoundRobinScheduler,
    create_scheduler,
)
from src.worker import Worker, WorkerSpec, validate_weight
from src.workload_generator import Task

from ..tasks import estimate_seconds, validate_task

PENDING = "pending"      # waiting in the scheduler (central queue or backlog)
QUEUED = "queued"        # placed in one worker's queue (RR/WRR/LL)
RUNNING = "running"      # delivered to a worker
COMPLETED = "completed"
FAILED = "failed"
ACTIVE_STATES = (PENDING, QUEUED, RUNNING)

W_ACTIVE = "active"
W_UNAVAILABLE = "unavailable"  # heartbeat late: receives no new tasks, keeps its queue
W_FAILED = "failed"            # heartbeat missing too long / restarted: its tasks are recovered


class ConflictError(RuntimeError):
    pass


@dataclass
class LiveTask:
    task_id: int
    task_type: str
    units: int
    estimated_seconds: float
    size_class: str
    label: str
    submitted_at: float
    submitted_unix: float
    sched_task: Task
    status: str = PENDING
    worker_id: str | None = None
    attempts: int = 0
    delivered_at: float | None = None
    completed_at: float | None = None
    exec_seconds: float | None = None
    cpu_seconds: float | None = None
    round_trip_seconds: float | None = None
    result: dict | None = None
    error: str | None = None
    history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {
            k: getattr(self, k)
            for k in (
                "task_id", "task_type", "units", "estimated_seconds", "size_class", "label", "status",
                "worker_id", "attempts", "submitted_at", "submitted_unix", "delivered_at", "completed_at",
                "exec_seconds", "cpu_seconds", "round_trip_seconds", "result", "error", "history",
            )
        }
        d["waiting_seconds"] = (
            None if self.delivered_at is None else round(self.delivered_at - self.submitted_at, 6)
        )
        d["turnaround_seconds"] = (
            None if self.completed_at is None else round(self.completed_at - self.submitted_at, 6)
        )
        d["network_overhead_seconds"] = (
            None
            if self.round_trip_seconds is None or self.exec_seconds is None
            else round(self.round_trip_seconds - self.exec_seconds, 6)
        )
        return d


@dataclass
class WorkerState:
    spec: WorkerSpec
    mirror: Worker
    boot_id: str
    host: str
    status: str = W_ACTIVE
    registered_at: float = 0.0
    last_heartbeat: float = 0.0
    last_heartbeat_unix: float = 0.0
    failed_at: float | None = None
    unavailable_at: float | None = None
    waiter: asyncio.Future | None = None
    latest_metrics: dict = field(default_factory=dict)
    metrics_history: deque = field(default_factory=lambda: deque(maxlen=1800))
    failures: int = 0
    recoveries: int = 0
    info: dict = field(default_factory=dict)

    @property
    def worker_id(self) -> str:
        return self.spec.worker_id


class Cluster:
    def __init__(
        self,
        algorithm: str = "least_loaded",
        heartbeat_interval: float = 2.0,
        unavailable_after: float = 5.0,
        failed_after: float = 10.0,
        max_attempts: int = 3,
        clock: Callable[[], float] = time.monotonic,
        wallclock: Callable[[], float] = time.time,
    ) -> None:
        if not 0 < unavailable_after <= failed_after:
            raise ValueError("need 0 < unavailable_after <= failed_after")
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self.heartbeat_interval = heartbeat_interval
        self.unavailable_after = unavailable_after
        self.failed_after = failed_after
        self.max_attempts = max_attempts
        self._clock = clock
        self._wall = wallclock
        self._t0 = clock()
        self.workers: dict[str, WorkerState] = {}
        self.tasks: dict[int, LiveTask] = {}
        self.events: deque[dict] = deque(maxlen=5000)
        self.runs: list[dict] = []
        self.counters = {k: 0 for k in (
            "submitted", "completed", "failed", "retries", "requeued", "worker_failures",
            "worker_recoveries", "stale_results",
        )}
        self.on_complete: list[Callable[[LiveTask], None]] = []
        self._next_task_id = 1
        self._run_id = 1
        self._run_started = self.now()
        self._backlog: deque[Task] = deque()
        self.scheduler = create_scheduler(algorithm)
        self.algorithm = algorithm

    def now(self) -> float:
        return self._clock() - self._t0

    def _event(self, kind: str, worker_id: str | None = None, task_id: int | None = None, **detail: Any) -> None:
        self.events.append(
            {"t": round(self.now(), 4), "unix": round(self._wall(), 4), "run_id": self._run_id,
             "type": kind, "worker_id": worker_id, "task_id": task_id, **detail}
        )

    def mirrors(self) -> list[Worker]:
        return [self.workers[k].mirror for k in sorted(self.workers)]

    def active_task_count(self) -> int:
        return sum(1 for t in self.tasks.values() if t.status in ACTIVE_STATES)

    @property
    def central(self) -> bool:
        return isinstance(self.scheduler, CentralQueueScheduler)

    def set_algorithm(self, name: str) -> None:
        if name not in ALL_CONFIGURATIONS:
            raise ValueError(f"Unknown algorithm {name!r}; choose from {sorted(ALL_CONFIGURATIONS)}")
        if self.active_task_count():
            raise ConflictError("Cannot change algorithm while tasks are pending or running")
        self.scheduler = create_scheduler(name)
        self.scheduler.reset(self.mirrors())
        self.algorithm = name
        self._backlog.clear()
        self._event("algorithm_changed", algorithm=name)

    def reset_run(self, label: str = "") -> dict | None:
        if self.active_task_count():
            raise ConflictError("Cannot reset while tasks are pending or running")
        summary = None
        if self.tasks:
            summary = self.run_summary()
            self.runs.append(summary)
        self.tasks.clear()
        self._backlog.clear()
        for ws in self.workers.values():
            old = ws.mirror
            ws.mirror = Worker(ws.spec)
            ws.mirror.available = old.available
        self.scheduler.reset(self.mirrors())
        self._run_id += 1
        self._run_started = self.now()
        self._event("run_started", algorithm=self.algorithm, label=label)
        return summary

    def heartbeat(self, payload: dict) -> dict:
        wid = str(payload["worker_id"])
        now = self.now()
        boot_id = str(payload.get("boot_id", ""))
        ws = self.workers.get(wid)
        if ws is None:
            spec = WorkerSpec(
                worker_id=wid,
                capacity=float(payload.get("capacity", 1.0)),
                weight=validate_weight(int(payload.get("weight", 1)), wid),
            )
            ws = WorkerState(spec=spec, mirror=Worker(spec), boot_id=boot_id, host=str(payload.get("host", "")),
                             registered_at=now)
            self.workers[wid] = ws
            self._attach_to_scheduler(ws)
            self._event("worker_registered", wid, capacity=spec.capacity, weight=spec.weight, host=ws.host)
        elif boot_id and boot_id != ws.boot_id:
            # Same worker id, new process: anything it was running is lost.
            if ws.status != W_FAILED:
                self._fail_worker(ws, reason="worker process restarted")
            ws.boot_id = boot_id
            ws.host = str(payload.get("host", ws.host))
        ws.last_heartbeat = now
        ws.last_heartbeat_unix = self._wall()
        ws.info = {k: payload.get(k) for k in ("host", "pid", "cpu_limit_cores", "url", "version") if k in payload}
        metrics = payload.get("metrics") or {}
        if metrics:
            sample = {"t": round(now, 3), "unix": round(self._wall(), 3), **metrics}
            ws.latest_metrics = sample
            ws.metrics_history.append(sample)
        if ws.status != W_ACTIVE:
            self._recover_worker(ws)
        self.dispatch()
        return {"ok": True, "status": ws.status, "server_time": self._wall()}

    def _attach_to_scheduler(self, ws: WorkerState) -> None:
        if not self.active_task_count():
            self.scheduler.reset(self.mirrors())
            return
        # Mid-run join: extend scheduler bookkeeping without dropping queued tasks
        # (reset() would clear SJF/FCFS central queues).
        self.scheduler._index[ws.worker_id] = len(self.workers) - 1
        if isinstance(self.scheduler, WeightedRoundRobinScheduler):
            self.scheduler._weights[ws.worker_id] = ws.spec.weight
            self.scheduler._current[ws.worker_id] = 0

    def _recover_worker(self, ws: WorkerState) -> None:
        now = self.now()
        prev = ws.status
        downtime = None
        if prev == W_FAILED and ws.failed_at is not None:
            downtime = round(now - ws.failed_at, 4)
            ws.recoveries += 1
            self.counters["worker_recoveries"] += 1
        ws.status = W_ACTIVE
        ws.mirror.available = True
        ws.failed_at = ws.unavailable_at = None
        self._event("worker_recovered" if prev == W_FAILED else "worker_available", ws.worker_id,
                    previous_status=prev, downtime_seconds=downtime)

    def check_health(self) -> None:
        now = self.now()
        changed = False
        for ws in self.workers.values():
            age = now - ws.last_heartbeat
            if ws.status == W_ACTIVE and age > self.unavailable_after:
                ws.status = W_UNAVAILABLE
                ws.unavailable_at = now
                ws.mirror.available = False
                self._event("worker_unavailable", ws.worker_id, heartbeat_age_seconds=round(age, 3))
                changed = True
            if ws.status == W_UNAVAILABLE and age > self.failed_after:
                self._fail_worker(ws, reason=f"no heartbeat for {age:.1f}s", heartbeat_age=age)
                changed = True
        if changed:
            self.dispatch()

    def _fail_worker(self, ws: WorkerState, reason: str, heartbeat_age: float | None = None) -> None:
        now = self.now()
        ws.status = W_FAILED
        ws.failed_at = now
        ws.failures += 1
        self.counters["worker_failures"] += 1
        m = ws.mirror
        m.available = False
        interrupted = []
        if m.current_task is not None:
            interrupted.append(m.current_task)
            if m.current_start is not None:
                m.busy_time += now - m.current_start
            m.current_task = m.current_start = m.current_end = None
        queued = list(m.queue)
        m.queue.clear()
        if ws.waiter is not None and not ws.waiter.done():
            ws.waiter.cancel()
        ws.waiter = None
        self._event("worker_failed", ws.worker_id, reason=reason,
                    heartbeat_age_seconds=None if heartbeat_age is None else round(heartbeat_age, 3),
                    last_heartbeat_unix=round(ws.last_heartbeat_unix, 4),
                    interrupted_tasks=[t.task_id for t in interrupted], queued_tasks=[t.task_id for t in queued])
        # Recover in task-id order: interrupted (counts as a failed attempt) and queued (never started).
        for sched_task in sorted(interrupted + queued, key=lambda t: t.task_id, reverse=True):
            self._requeue(self.tasks[sched_task.task_id], interrupted=sched_task in interrupted,
                          reason=f"worker {ws.worker_id} failed")

    def _requeue(self, task: LiveTask, interrupted: bool, reason: str) -> None:
        prev_worker = task.worker_id
        task.history.append({"t": round(self.now(), 4), "event": "interrupted" if interrupted else "reassigned",
                             "worker_id": prev_worker, "attempt": task.attempts, "reason": reason})
        if interrupted and task.attempts >= self.max_attempts:
            task.status = FAILED
            task.error = f"gave up after {task.attempts} attempts ({reason})"
            task.completed_at = self.now()
            self.counters["failed"] += 1
            self._event("task_failed", prev_worker, task.task_id, attempts=task.attempts, reason=reason)
            return
        if interrupted:
            self.counters["retries"] += 1
        self.counters["requeued"] += 1
        task.status = PENDING
        task.worker_id = None
        task.delivered_at = None
        if self.central:
            self.scheduler.add_task(task.sched_task)
        else:
            # called in reverse id order, so appendleft leaves recovered tasks in id order at the front
            self._backlog.appendleft(task.sched_task)
        self._event("task_requeued", prev_worker, task.task_id, attempt=task.attempts, interrupted=interrupted)

    def submit(self, task_type: str, units: int, estimated_seconds: float | None = None,
               size_class: str = "", label: str = "") -> LiveTask:
        validate_task(task_type, units)
        est = estimate_seconds(task_type, units) if estimated_seconds is None else float(estimated_seconds)
        est = max(est, 1e-4)
        now = self.now()
        tid = self._next_task_id
        self._next_task_id += 1
        # actual_duration is unknown for real tasks; the field is required by Task but no
        # scheduler reads it (enforced by tests/test_no_actual_duration_leak.py).
        sched_task = Task(task_id=tid, arrival_time=round(now, 6), estimated_duration=est,
                          actual_duration=est, task_type=size_class or task_type)
        task = LiveTask(task_id=tid, task_type=task_type, units=units, estimated_seconds=est,
                        size_class=size_class, label=label, submitted_at=now, submitted_unix=self._wall(),
                        sched_task=sched_task)
        self.tasks[tid] = task
        self.counters["submitted"] += 1
        if self.central:
            self.scheduler.add_task(sched_task)
        elif self._backlog:
            self._backlog.append(sched_task)
        else:
            self._place(sched_task)
        self.dispatch()
        return task

    def _place(self, sched_task: Task) -> bool:
        worker = self.scheduler.select_worker(sched_task, self.mirrors(), self.now())
        if worker is None:
            self._backlog.append(sched_task)
            return False
        worker.enqueue(sched_task)
        t = self.tasks[sched_task.task_id]
        t.status = QUEUED
        t.worker_id = worker.worker_id
        return True

    def dispatch(self) -> None:
        now = self.now()
        sched = self.scheduler
        if isinstance(sched, CentralQueueScheduler):
            while sched.has_pending():
                idle = [ws.mirror for ws in self._ready_workers()]
                if not idle:
                    break
                mirror = sched.select_idle_worker(idle)
                sched_task = sched.pop_next_task(now, mirror)
                mirror.record_assignment(sched_task)
                self._deliver(self.workers[mirror.worker_id], sched_task)
            return
        assert isinstance(sched, PerWorkerQueueScheduler)
        while self._backlog:
            worker = sched.select_worker(self._backlog[0], self.mirrors(), now)
            if worker is None:
                break
            sched_task = self._backlog.popleft()
            worker.enqueue(sched_task)
            t = self.tasks[sched_task.task_id]
            t.status = QUEUED
            t.worker_id = worker.worker_id
        for ws in self._ready_workers():
            if ws.mirror.queue:
                self._deliver(ws, ws.mirror.queue.popleft())

    def _ready_workers(self) -> list[WorkerState]:
        return [
            self.workers[k] for k in sorted(self.workers)
            if self.workers[k].status == W_ACTIVE and self.workers[k].mirror.is_idle
            and self.workers[k].waiter is not None and not self.workers[k].waiter.done()
        ]

    def _deliver(self, ws: WorkerState, sched_task: Task) -> None:
        now = self.now()
        task = self.tasks[sched_task.task_id]
        ws.mirror.start(sched_task, now)
        task.status = RUNNING
        task.worker_id = ws.worker_id
        task.attempts += 1
        task.delivered_at = now
        task.history.append({"t": round(now, 4), "event": "delivered", "worker_id": ws.worker_id,
                             "attempt": task.attempts})
        assert ws.waiter is not None
        ws.waiter.set_result({"task_id": task.task_id, "attempt": task.attempts, "task_type": task.task_type,
                              "units": task.units})
        ws.waiter = None

    async def poll(self, worker_id: str, timeout: float) -> dict | None:
        ws = self.workers.get(worker_id)
        if ws is None:
            raise KeyError(worker_id)
        if ws.mirror.current_task is not None:
            # The worker loop only polls when idle, after reporting its last result, so a task
            # still marked running here was never received (lost delivery): retry it.
            lost = ws.mirror.current_task
            ws.mirror.current_task = ws.mirror.current_start = ws.mirror.current_end = None
            self._requeue(self.tasks[lost.task_id], interrupted=True, reason="delivery lost")
        if ws.waiter is not None and not ws.waiter.done():
            ws.waiter.cancel()
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        ws.waiter = fut
        self.dispatch()
        try:
            done, _ = await asyncio.wait({fut}, timeout=timeout)
        except asyncio.CancelledError:
            if ws.waiter is fut:
                ws.waiter = None
            raise
        if fut in done and not fut.cancelled():
            return fut.result()
        if ws.waiter is fut:
            ws.waiter = None
        if not fut.done():
            fut.cancel()
        return None

    def complete(self, task_id: int, worker_id: str, attempt: int, ok: bool, exec_seconds: float,
                 cpu_seconds: float | None = None, result: dict | None = None, error: str | None = None) -> dict:
        task = self.tasks.get(task_id)
        ws = self.workers.get(worker_id)
        if (task is None or ws is None or task.status != RUNNING or task.worker_id != worker_id
                or task.attempts != attempt or ws.mirror.current_task is None
                or ws.mirror.current_task.task_id != task_id):
            self.counters["stale_results"] += 1
            self._event("stale_result_discarded", worker_id, task_id, attempt=attempt)
            return {"accepted": False}
        now = self.now()
        ws.mirror.complete(now)
        task.completed_at = now
        task.exec_seconds = float(exec_seconds)
        task.cpu_seconds = None if cpu_seconds is None else float(cpu_seconds)
        task.round_trip_seconds = None if task.delivered_at is None else now - task.delivered_at
        task.history.append({"t": round(now, 4), "event": "completed" if ok else "error", "worker_id": worker_id,
                             "attempt": attempt})
        if ok:
            task.status = COMPLETED
            task.result = result
            self.counters["completed"] += 1
        else:
            # Task code raised: deterministic, so it is not retried.
            task.status = FAILED
            task.error = error or "task error"
            self.counters["failed"] += 1
            self._event("task_failed", worker_id, task_id, attempts=attempt, reason=task.error)
        for hook in self.on_complete:
            hook(task)
        self.dispatch()
        return {"accepted": True}

    def worker_view(self, ws: WorkerState) -> dict:
        m = ws.mirror
        return {
            "worker_id": ws.worker_id,
            "status": ws.status,
            "busy": m.current_task is not None,
            "current_task_id": None if m.current_task is None else m.current_task.task_id,
            "queue_length": len(m.queue),
            "capacity": ws.spec.capacity,
            "weight": ws.spec.weight,
            "host": ws.host,
            "assigned_tasks": m.tasks_assigned,
            "completed_tasks": m.tasks_completed,
            "estimated_load_seconds": round(m.estimated_load(self.now()), 4),
            "last_heartbeat_age_seconds": round(self.now() - ws.last_heartbeat, 3),
            "last_heartbeat_unix": round(ws.last_heartbeat_unix, 3),
            "failures": ws.failures,
            "recoveries": ws.recoveries,
            "metrics": ws.latest_metrics,
            "info": ws.info,
        }

    def run_summary(self) -> dict:
        tasks = list(self.tasks.values())
        done = [t for t in tasks if t.status == COMPLETED]
        n_failed = sum(1 for t in tasks if t.status == FAILED)
        first = min((t.submitted_at for t in tasks), default=self._run_started)
        last = max((t.completed_at for t in tasks if t.completed_at is not None), default=first)
        makespan = last - first

        def mean(xs: list[float]) -> float | None:
            return round(statistics.fmean(xs), 6) if xs else None

        per_worker: dict[str, int] = {}
        for t in done:
            per_worker[t.worker_id] = per_worker.get(t.worker_id, 0) + 1
        return {
            "run_id": self._run_id,
            "algorithm": self.algorithm,
            "submitted": len(tasks),
            "completed": len(done),
            "failed": n_failed,
            "pending": sum(1 for t in tasks if t.status in ACTIVE_STATES),
            "retries": sum(max(0, t.attempts - 1) for t in tasks),
            "makespan_seconds": round(makespan, 6),
            "throughput_tasks_per_second": round(len(done) / makespan, 6) if makespan > 0 else None,
            "avg_exec_seconds": mean([t.exec_seconds for t in done if t.exec_seconds is not None]),
            "avg_waiting_seconds": mean([t.delivered_at - t.submitted_at for t in done if t.delivered_at is not None]),
            "avg_turnaround_seconds": mean([t.completed_at - t.submitted_at for t in done]),
            "avg_network_overhead_seconds": mean(
                [t.round_trip_seconds - t.exec_seconds for t in done
                 if t.round_trip_seconds is not None and t.exec_seconds is not None]),
            "completed_per_worker": per_worker,
        }

    def stats(self) -> dict:
        tasks = list(self.tasks.values())
        by_status = {s: 0 for s in (PENDING, QUEUED, RUNNING, COMPLETED, FAILED)}
        for t in tasks:
            by_status[t.status] += 1
        return {
            "algorithm": self.algorithm,
            "dispatch_mode": self.scheduler.dispatch_mode,
            "run": self.run_summary(),
            "tasks_by_status": by_status,
            "backlog": len(self._backlog) + (self.scheduler.pending_count() if self.central else 0),
            "workers": {s: sum(1 for w in self.workers.values() if w.status == s)
                        for s in (W_ACTIVE, W_UNAVAILABLE, W_FAILED)},
            "lifetime_counters": dict(self.counters),
            "config": {"heartbeat_interval": self.heartbeat_interval, "unavailable_after": self.unavailable_after,
                       "failed_after": self.failed_after, "max_attempts": self.max_attempts},
            "uptime_seconds": round(self.now(), 3),
            "server_time": self._wall(),
        }

from __future__ import annotations

import asyncio
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from src.schedulers import ALL_CONFIGURATIONS, CentralQueueScheduler, PerWorkerQueueScheduler, create_scheduler
from src.worker import Worker, WorkerSpec
from src.workload_generator import Task

from .config import DEFAULT_ESTIMATES, FALLBACK_ESTIMATE, BackendConfig, Settings


class ConflictError(RuntimeError):
    pass


class QueueTimeout(RuntimeError):
    pass


class NoBackendAvailable(RuntimeError):
    pass


@dataclass
class RequestRecord:
    task_id: int
    route: str
    method: str
    path: str
    arrived: float
    task: Task
    backend_id: str | None = None
    dispatched: float | None = None
    finished: float | None = None
    status: int | None = None
    attempts: int = 0
    ok: bool | None = None

    @property
    def wait_seconds(self) -> float | None:
        return None if self.dispatched is None else self.dispatched - self.arrived

    @property
    def service_seconds(self) -> float | None:
        return None if self.finished is None or self.dispatched is None else self.finished - self.dispatched

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id, "route": self.route, "method": self.method, "path": self.path,
            "backend_id": self.backend_id, "status": self.status, "attempts": self.attempts, "ok": self.ok,
            "arrived": round(self.arrived, 4),
            "estimated_ms": round(self.task.estimated_duration * 1000, 2),
            "wait_ms": None if self.wait_seconds is None else round(self.wait_seconds * 1000, 2),
            "service_ms": None if self.service_seconds is None else round(self.service_seconds * 1000, 2),
        }


@dataclass
class Backend:
    config: BackendConfig
    mirror: Worker
    healthy: bool = True
    consecutive_failures: int = 0
    completed: int = 0
    errors: int = 0
    assigned: int = 0
    service_samples: deque = field(default_factory=lambda: deque(maxlen=500))
    wait_samples: deque = field(default_factory=lambda: deque(maxlen=500))
    busy_seconds: float = 0.0
    outage_until: float = 0.0     # simulated outage: health probes are ignored until this time

    @property
    def backend_id(self) -> str:
        return self.config.backend_id

    @property
    def inflight(self) -> int:
        return len(self.mirror.queue)

    def view(self, now: float) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "url": self.config.url,
            "capacity": self.config.capacity,
            "weight": self.config.weight,
            "slots": self.config.slots,
            "healthy": self.healthy,
            "inflight": self.inflight,
            "estimated_load_ms": round(self.mirror.estimated_load(now) * 1000, 2),
            "assigned": self.assigned,
            "completed": self.completed,
            "errors": self.errors,
            "avg_service_ms": _avg_ms(self.service_samples),
            "p95_service_ms": _p95_ms(self.service_samples),
            "avg_wait_ms": _avg_ms(self.wait_samples),
            "busy_seconds": round(self.busy_seconds, 3),
            "simulated_outage_remaining_s": round(max(0.0, self.outage_until - now), 1),
        }


def _avg_ms(samples: deque) -> float | None:
    return None if not samples else round(statistics.fmean(samples) * 1000, 2)


def _p95_ms(samples: deque) -> float | None:
    if not samples:
        return None
    s = sorted(samples)
    return round(s[min(len(s) - 1, int(0.95 * len(s)))] * 1000, 2)


# Not thread-safe: all methods must run on the single asyncio event loop.
class Dispatcher:

    def __init__(self, settings: Settings, now_fn=None) -> None:
        self.settings = settings
        self._now = now_fn or time.monotonic
        self._t0 = self._now()
        self.backends: dict[str, Backend] = {}
        for cfg in settings.backends:
            spec = WorkerSpec(worker_id=cfg.backend_id, capacity=cfg.capacity, weight=cfg.weight,
                              max_queue_length=cfg.slots)
            self.backends[cfg.backend_id] = Backend(config=cfg, mirror=Worker(spec))
        self.algorithm = settings.algorithm
        self.scheduler = create_scheduler(self.algorithm)
        self.scheduler.reset(self.mirrors())
        self.estimates: dict[str, float] = dict(DEFAULT_ESTIMATES)
        self.records: dict[int, RequestRecord] = {}
        self.recent: deque[dict] = deque(maxlen=settings.recent_limit)
        self.events: deque[dict] = deque(maxlen=200)
        self.runs: list[dict] = []
        self.run_id = 1
        self.run_started = self.now()
        self._next_id = 1
        self._backlog: deque[Task] = deque()          # per-worker-queue algorithms: waiting requests
        self._waiters: dict[int, asyncio.Future] = {}  # task_id -> future resolved with Backend
        self._cancelled: set[int] = set()
        self._completion_times: deque[float] = deque(maxlen=5000)
        self.counters = {"received": 0, "dispatched": 0, "completed": 0, "errors": 0, "retries": 0,
                         "queue_timeouts": 0, "no_backend": 0}
        self._run_wait: list[float] = []
        self._run_service: list[float] = []
        self._run_total: list[float] = []
        self._event("run_started", algorithm=self.algorithm)

    def now(self) -> float:
        return self._now() - self._t0

    def mirrors(self) -> list[Worker]:
        return [self.backends[k].mirror for k in self.backends]  # config order (RR/WRR tie-break)

    @property
    def central(self) -> bool:
        return isinstance(self.scheduler, CentralQueueScheduler)

    @property
    def dispatch_mode(self) -> str:
        return self.scheduler.dispatch_mode

    def _event(self, kind: str, **data: Any) -> None:
        self.events.append({"t": round(self.now(), 4), "unix": round(time.time(), 3), "run_id": self.run_id,
                            "type": kind, **data})

    def active_count(self) -> int:
        return sum(b.inflight for b in self.backends.values()) + self.backlog_count()

    def backlog_count(self) -> int:
        return (self.scheduler.pending_count() if self.central else len(self._backlog))

    def estimate_for(self, route: str) -> float:
        return self.estimates.get(route, FALLBACK_ESTIMATE)

    def set_algorithm(self, name: str) -> None:
        if name not in ALL_CONFIGURATIONS:
            raise ValueError(f"Unknown algorithm {name!r}; choose from {sorted(ALL_CONFIGURATIONS)}")
        if name == self.algorithm:
            return
        if self.backlog_count():
            raise ConflictError("Cannot change algorithm while requests are queued; retry in a moment")
        self.scheduler = create_scheduler(name)
        self.scheduler.reset(self.mirrors())
        self.algorithm = name
        self._event("algorithm_changed", algorithm=name)

    def reset_run(self, label: str = "") -> dict:
        summary = self.run_summary(label)
        self.runs.append(summary)
        for b in self.backends.values():
            b.completed = b.errors = b.assigned = 0
            b.service_samples.clear()
            b.wait_samples.clear()
            b.busy_seconds = 0.0
        self._run_wait.clear()
        self._run_service.clear()
        self._run_total.clear()
        self.recent.clear()
        self.run_id += 1
        self.run_started = self.now()
        self._event("run_started", algorithm=self.algorithm, label=label)
        return summary

    def run_summary(self, label: str = "") -> dict:
        completed = len(self._run_total)
        elapsed = max(self.now() - self.run_started, 1e-9)
        per_backend = {k: b.completed for k, b in self.backends.items()}
        total_done = sum(per_backend.values()) or 1
        return {
            "run_id": self.run_id,
            "label": label,
            "algorithm": self.algorithm,
            "dispatch_mode": self.dispatch_mode,
            "started_unix": round(time.time() - (self.now() - self.run_started), 3),
            "duration_seconds": round(elapsed, 3),
            "completed": completed,
            "errors": sum(b.errors for b in self.backends.values()),
            "throughput_rps": round(completed / elapsed, 3),
            "avg_wait_ms": _avg_ms(deque(self._run_wait)),
            "avg_service_ms": _avg_ms(deque(self._run_service)),
            "avg_total_ms": _avg_ms(deque(self._run_total)),
            "p95_total_ms": _p95_ms(deque(self._run_total)),
            "completed_per_backend": per_backend,
            "share_per_backend": {k: round(100 * v / total_done, 1) for k, v in per_backend.items()},
        }

    def set_health(self, backend_id: str, healthy: bool) -> None:
        b = self.backends[backend_id]
        if b.healthy == healthy:
            return
        b.healthy = healthy
        b.mirror.available = healthy
        self._event("backend_recovered" if healthy else "backend_unavailable", backend_id=backend_id)
        if healthy:
            self._dispatch()

    def simulate_outage(self, backend_id: str, seconds: float) -> dict:
        if backend_id not in self.backends:
            raise KeyError(backend_id)
        if not 1 <= seconds <= 600:
            raise ValueError("seconds must be between 1 and 600")
        others = [b for k, b in self.backends.items() if k != backend_id and b.healthy]
        if not others:
            raise ConflictError("Refusing to take down the last healthy backend")
        b = self.backends[backend_id]
        b.outage_until = self.now() + seconds
        self._event("backend_outage_simulated", backend_id=backend_id, seconds=seconds)
        self.set_health(backend_id, False)
        return {"backend_id": backend_id, "seconds": seconds}

    def report_probe(self, backend_id: str, ok: bool) -> None:
        b = self.backends[backend_id]
        if ok and self.now() < b.outage_until:
            return
        if ok:
            b.consecutive_failures = 0
            self.set_health(backend_id, True)
        else:
            b.consecutive_failures += 1
            if b.consecutive_failures >= self.settings.unhealthy_after:
                self.set_health(backend_id, False)

    def submit(self, method: str, path: str, route: str) -> RequestRecord:
        now = self.now()
        tid = self._next_id
        self._next_id += 1
        est = max(self.estimate_for(route), 1e-4)
        # actual_duration is unknown for a real request; no scheduler reads it.
        task = Task(task_id=tid, arrival_time=round(now, 6), estimated_duration=est, actual_duration=est,
                    task_type=route)
        rec = RequestRecord(task_id=tid, route=route, method=method, path=path, arrived=now, task=task)
        self.records[tid] = rec
        self.counters["received"] += 1
        return rec

    async def acquire(self, rec: RequestRecord) -> Backend:
        if not any(b.healthy for b in self.backends.values()):
            self.counters["no_backend"] += 1
            raise NoBackendAvailable("no healthy backend")
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._waiters[rec.task_id] = fut
        if self.central:
            self.scheduler.add_task(rec.task)
        else:
            self._backlog.append(rec.task)
        self._dispatch()
        try:
            backend = await asyncio.wait_for(fut, timeout=self.settings.queue_timeout)
        except asyncio.TimeoutError:
            self._cancelled.add(rec.task_id)
            self._waiters.pop(rec.task_id, None)
            if not self.central:
                try:
                    self._backlog.remove(rec.task)
                except ValueError:
                    pass
            self.counters["queue_timeouts"] += 1
            raise QueueTimeout(f"request waited more than {self.settings.queue_timeout}s for a backend")
        return backend

    def _assign(self, backend: Backend, task: Task) -> None:
        rec = self.records[task.task_id]
        rec.backend_id = backend.backend_id
        rec.dispatched = self.now()
        rec.attempts += 1
        backend.assigned += 1
        self.counters["dispatched"] += 1
        fut = self._waiters.pop(task.task_id, None)
        if fut is not None and not fut.done():
            fut.set_result(backend)

    def _dispatch(self) -> None:
        now = self.now()
        sched = self.scheduler
        if isinstance(sched, CentralQueueScheduler):
            while sched.has_pending():
                free = [b.mirror for b in self.backends.values() if b.mirror.can_accept()]
                if not free:
                    break
                mirror = sched.select_idle_worker(free)
                task = sched.pop_next_task(now, mirror)
                if task.task_id in self._cancelled:
                    self._cancelled.discard(task.task_id)
                    continue
                mirror.queue.append(task)          # queue == requests in flight on this backend
                mirror.record_assignment(task)
                self._assign(self.backends[mirror.worker_id], task)
            return
        assert isinstance(sched, PerWorkerQueueScheduler)
        while self._backlog:
            task = self._backlog[0]
            if task.task_id in self._cancelled:
                self._cancelled.discard(task.task_id)
                self._backlog.popleft()
                continue
            mirror = sched.select_worker(task, self.mirrors(), now)
            if mirror is None:
                break
            self._backlog.popleft()
            mirror.enqueue(task)
            self._assign(self.backends[mirror.worker_id], task)

    def release(self, rec: RequestRecord, backend: Backend, status: int | None, ok: bool,
                retry: bool = False) -> None:
        now = self.now()
        try:
            backend.mirror.queue.remove(rec.task)
        except ValueError:
            pass
        service = None if rec.dispatched is None else now - rec.dispatched
        if service is not None:
            backend.busy_seconds += service
        if retry:
            self.counters["retries"] += 1
            backend.errors += 1
            self._event("request_retried", backend_id=backend.backend_id, task_id=rec.task_id, route=rec.route)
            rec.dispatched = None
            rec.backend_id = None
        else:
            rec.finished = now
            rec.status = status
            rec.ok = ok
            if ok:
                backend.completed += 1
                self.counters["completed"] += 1
                if service is not None:
                    backend.service_samples.append(service)
                    self._run_service.append(service)
                    a = self.settings.ewma_alpha
                    self.estimates[rec.route] = a * service + (1 - a) * self.estimate_for(rec.route)
                if rec.wait_seconds is not None:
                    backend.wait_samples.append(rec.wait_seconds)
                    self._run_wait.append(rec.wait_seconds)
                self._run_total.append(now - rec.arrived)
                self._completion_times.append(now)
            else:
                backend.errors += 1
                self.counters["errors"] += 1
            self.recent.append(rec.to_dict())
            self.records.pop(rec.task_id, None)
        self._dispatch()

    def throughput(self, window: float = 30.0) -> float:
        now = self.now()
        n = sum(1 for t in self._completion_times if t > now - window)
        return round(n / window, 3)

    def stats(self) -> dict[str, Any]:
        now = self.now()
        return {
            "algorithm": self.algorithm,
            "dispatch_mode": self.dispatch_mode,
            "algorithms": sorted(ALL_CONFIGURATIONS),
            "run_id": self.run_id,
            "run": self.run_summary(),
            "uptime_seconds": round(now, 1),
            "backlog": self.backlog_count(),
            "inflight": sum(b.inflight for b in self.backends.values()),
            "throughput_rps_30s": self.throughput(30.0),
            "counters": dict(self.counters),
            "backends": [b.view(now) for b in self.backends.values()],
            "route_estimates_ms": {k: round(v * 1000, 2) for k, v in sorted(self.estimates.items())},
            "queue_timeout_seconds": self.settings.queue_timeout,
        }

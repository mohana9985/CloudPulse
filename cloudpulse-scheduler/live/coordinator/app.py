from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Histogram, generate_latest
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily
from pydantic import BaseModel, Field

from src.schedulers import ALGORITHMS, CONTROL_BASELINES, DISPLAY_NAMES, create_scheduler

from ..tasks import TASK_FUNCTIONS, generate_live_workload, live_workload_fingerprint
from .cluster import ACTIVE_STATES, W_ACTIVE, Cluster, ConflictError, LiveTask


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def build_cluster() -> Cluster:
    return Cluster(
        algorithm=os.environ.get("ALGORITHM", "least_loaded"),
        heartbeat_interval=_env_float("HEARTBEAT_INTERVAL", 2.0),
        unavailable_after=_env_float("UNAVAILABLE_AFTER", 5.0),
        failed_after=_env_float("FAILED_AFTER", 10.0),
        max_attempts=int(os.environ.get("MAX_ATTEMPTS", 3)),
    )


POLL_MAX_WAIT = _env_float("POLL_MAX_WAIT", 20.0)


class TaskIn(BaseModel):
    task_type: str
    units: int = Field(ge=1)
    estimated_seconds: float | None = Field(default=None, gt=0)
    size_class: str = ""
    label: str = ""


class BatchIn(BaseModel):
    tasks: list[TaskIn] = Field(min_length=1, max_length=2000)


class WorkloadIn(BaseModel):
    num_tasks: int = Field(ge=1, le=1000)
    seed: int = 42
    load: float = Field(default=0.85, gt=0, le=3.0)
    label: str = ""
    # Fix the arrival rate independently of how many workers are up (scalability runs).
    total_capacity: float | None = Field(default=None, gt=0)


class HeartbeatIn(BaseModel):
    worker_id: str = Field(min_length=1, max_length=64)
    boot_id: str = ""
    capacity: float = Field(default=1.0, gt=0)
    weight: int = Field(default=1, ge=1)
    host: str = ""
    pid: int | None = None
    cpu_limit_cores: float | None = None
    url: str | None = None
    version: str | None = None
    state: Literal["idle", "busy"] = "idle"
    metrics: dict = Field(default_factory=dict)


class ResultIn(BaseModel):
    worker_id: str
    attempt: int = Field(ge=1)
    ok: bool
    exec_seconds: float = Field(ge=0)
    cpu_seconds: float | None = None
    result: dict | None = None
    error: str | None = None


class AlgorithmIn(BaseModel):
    algorithm: str


class ResetIn(BaseModel):
    label: str = ""


class ClusterCollector:
    def __init__(self, app: FastAPI) -> None:
        self.app = app

    def collect(self):
        cluster: Cluster = self.app.state.cluster
        c = cluster.counters
        for key, help_ in (
            ("submitted", "Tasks submitted"), ("completed", "Tasks completed successfully"),
            ("failed", "Tasks that failed permanently"), ("retries", "Task retries after an interrupted attempt"),
            ("worker_failures", "Worker failures detected"), ("worker_recoveries", "Worker recoveries"),
        ):
            yield CounterMetricFamily(f"cloudpulse_sched_{key}", help_, value=c[key])
        g = GaugeMetricFamily("cloudpulse_sched_tasks", "Tasks in the current run by status", labels=["status"])
        for status, n in cluster.stats()["tasks_by_status"].items():
            g.add_metric([status], n)
        yield g
        up = GaugeMetricFamily("cloudpulse_worker_up", "1 if worker is active (heartbeats OK)", labels=["worker"])
        cpu = GaugeMetricFamily("cloudpulse_worker_cpu_percent_of_limit",
                                "Worker process CPU as % of its container CPU limit", labels=["worker"])
        mem = GaugeMetricFamily("cloudpulse_worker_memory_bytes", "Worker container memory (cgroup) or RSS",
                                labels=["worker"])
        done = GaugeMetricFamily("cloudpulse_worker_completed_tasks", "Tasks completed in the current run",
                                 labels=["worker"])
        for wid, ws in sorted(cluster.workers.items()):
            up.add_metric([wid], 1.0 if ws.status == W_ACTIVE else 0.0)
            m = ws.latest_metrics
            if m.get("cpu_percent_of_limit") is not None:
                cpu.add_metric([wid], float(m["cpu_percent_of_limit"]))
            mem_mb = m.get("container_memory_mb") or m.get("process_rss_mb")
            if mem_mb is not None:
                mem.add_metric([wid], float(mem_mb) * 1024 * 1024)
            done.add_metric([wid], ws.mirror.tasks_completed)
        yield from (up, cpu, mem, done)
        alg = GaugeMetricFamily("cloudpulse_sched_algorithm_info", "Active algorithm", labels=["algorithm"])
        alg.add_metric([cluster.algorithm], 1)
        yield alg


def create_app(cluster_factory=build_cluster, monitor_interval: float = 0.5) -> FastAPI:
    registry = CollectorRegistry()
    exec_hist = Histogram("cloudpulse_task_exec_seconds", "Task execution time measured by the worker",
                          ["worker", "algorithm"], registry=registry,
                          buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 16))
    turn_hist = Histogram("cloudpulse_task_turnaround_seconds", "Submit -> result time at the coordinator",
                          ["algorithm"], registry=registry, buckets=(0.1, 0.25, 0.5, 1, 2, 4, 8, 16, 32, 64))

    def observe(task: LiveTask) -> None:
        if task.exec_seconds is not None and task.worker_id:
            exec_hist.labels(task.worker_id, app.state.cluster.algorithm).observe(task.exec_seconds)
        if task.completed_at is not None:
            turn_hist.labels(app.state.cluster.algorithm).observe(task.completed_at - task.submitted_at)

    async def monitor() -> None:
        while True:
            await asyncio.sleep(monitor_interval)
            app.state.cluster.check_health()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        mon = asyncio.create_task(monitor())
        try:
            yield
        finally:
            mon.cancel()
            wl = app.state.workload_task
            if wl is not None:
                wl.cancel()

    app = FastAPI(title="CloudPulse Scheduler Coordinator", version="1.0.0", lifespan=lifespan)
    app.state.cluster = cluster_factory()
    app.state.cluster.on_complete.append(observe)
    app.state.workload_task = None
    app.state.workload_info = None
    registry.register(ClusterCollector(app))

    def cluster() -> Cluster:
        return app.state.cluster

    @app.get("/health")
    def health():
        c = cluster()
        return {"status": "ok", "algorithm": c.algorithm, "active_workers": c.stats()["workers"][W_ACTIVE],
                "server_time": c._wall(), "uptime_seconds": round(c.now(), 3)}

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    @app.get("/scheduler/algorithms")
    def algorithms():
        def row(name, role):
            s = create_scheduler(name)
            return {"name": name, "display_name": DISPLAY_NAMES[name], "role": role,
                    "dispatch_mode": s.dispatch_mode}
        return {"active": cluster().algorithm,
                "algorithms": [row(n, "primary") for n in ALGORITHMS] + [row(n, "control") for n in CONTROL_BASELINES]}

    @app.post("/scheduler/algorithm")
    def set_algorithm(body: AlgorithmIn):
        try:
            cluster().set_algorithm(body.algorithm)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except ConflictError as e:
            raise HTTPException(409, str(e))
        return {"active": cluster().algorithm}

    @app.get("/scheduler/stats")
    def stats():
        s = cluster().stats()
        s["workload"] = app.state.workload_info
        return s

    @app.post("/scheduler/reset")
    def reset(body: ResetIn | None = None):
        wl = app.state.workload_task
        if wl is not None and not wl.done():
            raise HTTPException(409, "A workload is still being submitted")
        try:
            summary = cluster().reset_run(label=body.label if body else "")
        except ConflictError as e:
            raise HTTPException(409, str(e))
        app.state.workload_info = None
        return {"archived_run": summary}

    @app.get("/scheduler/runs")
    def runs():
        c = cluster()
        current = c.run_summary() if c.tasks else None
        return {"runs": c.runs, "current": current}

    @app.get("/events")
    def events(since: float = 0.0, limit: int = Query(500, ge=1, le=5000)):
        evs = [e for e in cluster().events if e["t"] > since]
        return {"events": evs[-limit:]}

    @app.post("/tasks/submit", status_code=201)
    def submit(body: TaskIn | BatchIn):
        items = body.tasks if isinstance(body, BatchIn) else [body]
        try:
            created = [cluster().submit(t.task_type, t.units, t.estimated_seconds, t.size_class, t.label)
                       for t in items]
        except ValueError as e:
            raise HTTPException(400, str(e))
        return {"task_ids": [t.task_id for t in created]}

    @app.get("/tasks/types")
    def task_types():
        return {"task_types": sorted(TASK_FUNCTIONS)}

    @app.get("/tasks")
    def list_tasks(status: str | None = None, limit: int = Query(200, ge=1, le=5000), offset: int = Query(0, ge=0)):
        tasks = sorted(cluster().tasks.values(), key=lambda t: t.task_id)
        if status:
            tasks = [t for t in tasks if t.status == status]
        return {"total": len(tasks), "tasks": [t.to_dict() for t in tasks[offset:offset + limit]]}

    @app.get("/tasks/{task_id}")
    def get_task(task_id: int):
        t = cluster().tasks.get(task_id)
        if t is None:
            raise HTTPException(404, "task not found")
        return t.to_dict()

    @app.post("/tasks/{task_id}/result")
    def task_result(task_id: int, body: ResultIn):
        return cluster().complete(task_id, body.worker_id, body.attempt, body.ok, body.exec_seconds,
                                  body.cpu_seconds, body.result, body.error)

    @app.post("/workloads/start", status_code=202)
    async def start_workload(body: WorkloadIn):
        c = cluster()
        wl = app.state.workload_task
        if (wl is not None and not wl.done()) or c.active_task_count():
            raise HTTPException(409, "A workload is already running")
        cap = body.total_capacity or sum(ws.spec.capacity for ws in c.workers.values() if ws.status == W_ACTIVE)
        if cap <= 0 or not any(ws.status == W_ACTIVE for ws in c.workers.values()):
            raise HTTPException(409, "No active workers")
        specs = generate_live_workload(body.num_tasks, body.seed, cap, body.load)
        info = {"num_tasks": body.num_tasks, "seed": body.seed, "load": body.load, "label": body.label,
                "algorithm": c.algorithm, "fingerprint": live_workload_fingerprint(specs), "submitted": 0,
                "total_capacity": cap, "duration_seconds": specs[-1].offset}
        app.state.workload_info = info

        async def replay():
            start = asyncio.get_running_loop().time()
            for s in specs:
                delay = start + s.offset - asyncio.get_running_loop().time()
                if delay > 0:
                    await asyncio.sleep(delay)
                c.submit(s.task_type, s.units, s.estimated_seconds, s.size_class, body.label)
                info["submitted"] += 1

        app.state.workload_task = asyncio.create_task(replay())
        return info

    @app.post("/workers/heartbeat")
    def heartbeat(body: HeartbeatIn):
        try:
            return cluster().heartbeat(body.model_dump())
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.get("/workers")
    def workers():
        c = cluster()
        return {"workers": [c.worker_view(c.workers[k]) for k in sorted(c.workers)]}

    @app.get("/workers/{worker_id}")
    def worker(worker_id: str):
        c = cluster()
        if worker_id not in c.workers:
            raise HTTPException(404, "worker not found")
        return c.worker_view(c.workers[worker_id])

    @app.get("/workers/{worker_id}/metrics")
    def worker_metrics(worker_id: str, since: float = 0.0):
        c = cluster()
        if worker_id not in c.workers:
            raise HTTPException(404, "worker not found")
        return {"worker_id": worker_id, "samples": [s for s in c.workers[worker_id].metrics_history if s["t"] > since]}

    @app.post("/workers/{worker_id}/poll")
    async def poll(worker_id: str, wait: float = Query(POLL_MAX_WAIT, gt=0, le=60)):
        try:
            assignment = await cluster().poll(worker_id, wait)
        except KeyError:
            raise HTTPException(404, "unknown worker: send a heartbeat first")
        if assignment is None:
            return Response(status_code=204)
        return assignment

    return app


app = create_app()

__all__ = ["app", "create_app", "ACTIVE_STATES"]

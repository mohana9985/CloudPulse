from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field

from .engine import MIXES, RequestResult, Run, RunConfig, build_plan, execute, fetch_catalog

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(),
                    format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("loadgen")
logging.getLogger("httpx").setLevel(logging.WARNING)

MAX_RUNS_KEPT = 50


class StartIn(BaseModel):
    num_requests: int = Field(500, ge=1, le=100_000)
    rate: float = Field(20.0, ge=0.1, le=1000)
    mix: str = "mixed"
    seed: int = Field(42, ge=0, le=1_000_000)
    max_concurrency: int = Field(64, ge=1, le=500)
    label: str = Field("", max_length=80)


class Metrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.requests = Counter("loadgen_requests_total", "Website requests sent by the workload generator",
                                ["kind", "outcome", "backend"], registry=self.registry)
        self.latency = Histogram("loadgen_request_latency_seconds", "End-to-end latency seen by the client",
                                 ["kind"], registry=self.registry,
                                 buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30))
        self.active = Gauge("loadgen_run_active", "1 while a website workload is running", registry=self.registry)
        self.target = Gauge("loadgen_target_rps", "Target arrival rate of the running workload",
                            registry=self.registry)
        self.inflight = Gauge("loadgen_inflight_requests", "Requests currently in flight", registry=self.registry)
        self.progress = Gauge("loadgen_run_progress_ratio", "Completed / planned requests of the current run",
                              registry=self.registry)

    def observe(self, r: RequestResult) -> None:
        self.requests.labels(r.kind, r.outcome, r.backend or "none").inc()
        self.latency.labels(r.kind).observe(r.latency_ms / 1000)


def create_app(target_url: str | None = None, transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    target = (target_url or os.getenv("TARGET_URL", "http://frontend")).rstrip("/")
    timeout = float(os.getenv("REQUEST_TIMEOUT", "30"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        limits = httpx.Limits(max_connections=500, max_keepalive_connections=100)
        app.state.client = httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=5.0), limits=limits,
                                             transport=transport)
        app.state.metrics = Metrics()
        app.state.run = None
        app.state.task = None
        app.state.runs = []
        app.state.next_id = 1
        logger.info("loadgen up: target=%s", target)
        yield
        if app.state.task and not app.state.task.done():
            app.state.task.cancel()
            try:
                await app.state.task
            except (asyncio.CancelledError, Exception):
                pass
        await app.state.client.aclose()

    app = FastAPI(title="CloudPulse website workload generator", lifespan=lifespan,
                  docs_url="/loadgen/docs", openapi_url="/loadgen/openapi.json", redoc_url=None)

    def running() -> bool:
        return app.state.task is not None and not app.state.task.done()

    @app.get("/loadgen/health")
    def health():
        return {"status": "ok", "target": target, "running": running()}

    @app.get("/loadgen/config")
    def config():
        return {"target": target, "mixes": MIXES, "limits": {"num_requests": [1, 100_000], "rate": [0.1, 1000],
                                                              "max_concurrency": [1, 500]}}

    @app.post("/loadgen/start", status_code=202)
    async def start(body: StartIn):
        if running():
            raise HTTPException(409, "A website workload is already running")
        cfg = RunConfig(body.num_requests, body.rate, body.mix, body.seed, body.max_concurrency, body.label)
        try:
            cfg.validate()
        except ValueError as e:
            raise HTTPException(400, str(e))
        catalog = await fetch_catalog(app.state.client, target)
        plan = build_plan(cfg, catalog)
        run = Run(run_id=app.state.next_id, config=cfg, plan_size=len(plan))
        app.state.next_id += 1
        app.state.run = run
        m: Metrics = app.state.metrics

        def observe(r: RequestResult) -> None:
            m.observe(r)
            m.inflight.set(run.inflight - 1)
            m.progress.set(len(run.results) / run.plan_size)

        async def go() -> None:
            m.active.set(1)
            m.target.set(cfg.rate)
            m.progress.set(0)
            try:
                await execute(run, plan, app.state.client, target, observe)
            finally:
                m.active.set(0)
                m.target.set(0)
                m.inflight.set(0)
                app.state.runs.append(run.summary())
                del app.state.runs[:-MAX_RUNS_KEPT]
                logger.info("run %s %s: %s requests", run.run_id, run.state, len(run.results))

        app.state.task = asyncio.create_task(go())
        return {"run_id": run.run_id, "planned": len(plan), "duration_seconds": plan[-1].offset,
                "target": target, "products_in_catalog": len(catalog["product_ids"])}

    @app.post("/loadgen/stop")
    async def stop():
        run: Run | None = app.state.run
        if not running() or run is None:
            raise HTTPException(409, "No website workload is running")
        run.stop_requested = True
        return {"run_id": run.run_id, "stopping": True}

    @app.get("/loadgen/status")
    def status():
        run: Run | None = app.state.run
        return {"running": running(), "target": target, "run": run.summary() if run else None}

    @app.get("/loadgen/recent")
    def recent(limit: int = 100):
        run: Run | None = app.state.run
        if run is None:
            return {"items": []}
        items = list(run.recent)[-max(1, min(limit, 300)):]
        return {"run_id": run.run_id, "items": [r.to_dict() for r in reversed(items)]}

    @app.get("/loadgen/runs")
    def runs():
        return {"runs": app.state.runs}

    @app.get("/metrics")
    def metrics():
        return Response(content=generate_latest(app.state.metrics.registry), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from .agent import WorkerAgent
from .metrics import MetricsSampler

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))


def build_agent() -> WorkerAgent:
    limit = os.environ.get("CPU_LIMIT_CORES")
    return WorkerAgent(
        worker_id=os.environ.get("WORKER_ID", "W1"),
        coordinator_url=os.environ.get("COORDINATOR_URL", "http://localhost:8100"),
        capacity=float(os.environ.get("CAPACITY", 1.0)),
        weight=int(os.environ.get("WEIGHT", 1)),
        heartbeat_interval=float(os.environ.get("HEARTBEAT_INTERVAL", 2.0)),
        poll_wait=float(os.environ.get("POLL_WAIT", 20.0)),
        sampler=MetricsSampler(float(limit) if limit else None),
        url=os.environ.get("WORKER_URL"),
    )


def create_app(agent_factory=build_agent) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        agent: WorkerAgent = app.state.agent
        loops = [asyncio.create_task(agent.heartbeat_loop()), asyncio.create_task(agent.work_loop())]
        try:
            yield
        finally:
            agent.stop()
            for t in loops:
                t.cancel()
            await agent.client.aclose()

    app = FastAPI(title="CloudPulse Worker", version="1.0.0", lifespan=lifespan)
    app.state.agent = agent_factory()

    @app.get("/health")
    def health():
        a: WorkerAgent = app.state.agent
        return {"status": "outage" if a.in_outage() else "ok", "worker_id": a.worker_id, "state": a.state,
                "last_heartbeat_ok_unix": a.last_heartbeat_ok}

    @app.get("/status")
    def status():
        a: WorkerAgent = app.state.agent
        return {"worker_id": a.worker_id, "boot_id": a.boot_id, "host": a.host, "capacity": a.capacity,
                "weight": a.weight, "state": a.state, "current_task": a.current_task, "completed": a.completed,
                "errors": a.errors, "coordinator_url": a.coordinator_url, "in_outage": a.in_outage()}

    @app.get("/metrics")
    def metrics():
        return app.state.agent.sampler.sample()

    @app.post("/admin/simulate-outage")
    def simulate_outage(seconds: float = Query(30.0, gt=0, le=600)):
        # Simulated network partition: no heartbeats, no polling, results not reported.
        # A real crash is tested with `docker stop` (see live/README.md).
        if os.environ.get("ENABLE_CHAOS", "false").lower() != "true":
            raise HTTPException(403, "chaos endpoints disabled (set ENABLE_CHAOS=true)")
        app.state.agent.simulate_outage(seconds)
        return {"outage_seconds": seconds}

    return app


app = create_app()

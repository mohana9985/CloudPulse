from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel

from .config import Settings, load_settings, route_key
from .dispatcher import Backend, ConflictError, Dispatcher, NoBackendAvailable, QueueTimeout, RequestRecord

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(),
                    format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("gateway")
logging.getLogger("httpx").setLevel(logging.WARNING)   # one line per proxied request is too noisy

HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
              "transfer-encoding", "upgrade", "host", "content-length"}

REQUESTS_TOTAL = Counter("gateway_requests_total", "Requests routed by the gateway",
                         ["backend", "route", "status_class"])
QUEUE_WAIT = Histogram("gateway_queue_wait_seconds", "Time a request waited for a backend slot", ["backend"],
                       buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10))
SERVICE_TIME = Histogram("gateway_service_seconds", "Backend service time seen by the gateway", ["backend"],
                         buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5))
INFLIGHT = Gauge("gateway_inflight_requests", "Requests in flight per backend", ["backend"])
BACKEND_UP = Gauge("gateway_backend_up", "1 if the backend passes health probes", ["backend"])
BACKLOG = Gauge("gateway_backlog_requests", "Requests waiting for a backend slot")
ALGORITHM = Gauge("gateway_algorithm_active", "1 for the active scheduling algorithm", ["algorithm"])
RETRIES = Counter("gateway_retries_total", "Requests re-dispatched after a backend connection failure")
QUEUE_TIMEOUTS = Counter("gateway_queue_timeouts_total", "Requests rejected after waiting too long")


class AlgorithmIn(BaseModel):
    algorithm: str


class ResetIn(BaseModel):
    label: str = ""


class OutageIn(BaseModel):
    seconds: float = 20


class CrashIn(BaseModel):
    down_seconds: float = 15


def _status_class(status: int) -> str:
    return f"{status // 100}xx"


def create_app(settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        dispatcher = Dispatcher(settings)
        app.state.dispatcher = dispatcher
        timeout = httpx.Timeout(settings.upstream_timeout, connect=3.0)
        limits = httpx.Limits(max_connections=200, max_keepalive_connections=50)
        app.state.client = httpx.AsyncClient(timeout=timeout, limits=limits, transport=transport)
        for alg in dispatcher.stats()["algorithms"]:
            ALGORITHM.labels(algorithm=alg).set(1 if alg == dispatcher.algorithm else 0)
        for b in dispatcher.backends.values():
            INFLIGHT.labels(backend=b.backend_id).set(0)
            BACKEND_UP.labels(backend=b.backend_id).set(1)
        app.state.health_task = asyncio.create_task(_health_loop(app, settings))
        logger.info("gateway up: algorithm=%s backends=%s", dispatcher.algorithm,
                    [(b.backend_id, b.config.url) for b in dispatcher.backends.values()])
        yield
        app.state.health_task.cancel()
        try:
            await app.state.health_task
        except (asyncio.CancelledError, Exception):
            pass
        await app.state.client.aclose()

    app = FastAPI(title="CloudPulse scheduling gateway", version=settings.app_version, lifespan=lifespan,
                  docs_url="/gateway/docs", openapi_url="/gateway/openapi.json", redoc_url=None)

    def disp() -> Dispatcher:
        return app.state.dispatcher

    @app.get("/gateway/health")
    def health():
        d = disp()
        healthy = [b.backend_id for b in d.backends.values() if b.healthy]
        return {"status": "ok" if healthy else "degraded", "algorithm": d.algorithm,
                "healthy_backends": healthy, "backends": len(d.backends)}

    @app.get("/gateway/stats")
    def stats():
        return disp().stats()

    @app.get("/gateway/recent")
    def recent(limit: int = 60):
        items = list(disp().recent)[-max(1, min(limit, 500)):]
        return {"items": list(reversed(items))}

    @app.get("/gateway/events")
    def events(limit: int = 50):
        items = list(disp().events)[-max(1, min(limit, 200)):]
        return {"events": list(reversed(items))}

    @app.get("/gateway/runs")
    def runs():
        return {"runs": disp().runs}

    @app.get("/gateway/backends")
    def backends():
        d = disp()
        return {"backends": [b.view(d.now()) for b in d.backends.values()]}

    @app.post("/gateway/algorithm")
    def set_algorithm(body: AlgorithmIn):
        d = disp()
        try:
            d.set_algorithm(body.algorithm)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except ConflictError as e:
            raise HTTPException(409, str(e))
        for alg in d.stats()["algorithms"]:
            ALGORITHM.labels(algorithm=alg).set(1 if alg == d.algorithm else 0)
        return {"active": d.algorithm, "dispatch_mode": d.dispatch_mode}

    @app.post("/gateway/reset")
    def reset(body: ResetIn | None = None):
        return {"archived_run": disp().reset_run(body.label if body else "")}

    @app.post("/gateway/backends/{backend_id}/outage")
    def simulate_outage(backend_id: str, body: OutageIn | None = None):
        d = disp()
        try:
            out = d.simulate_outage(backend_id, body.seconds if body else 20)
        except KeyError:
            raise HTTPException(404, f"Unknown backend {backend_id}")
        except ValueError as e:
            raise HTTPException(400, str(e))
        except ConflictError as e:
            raise HTTPException(409, str(e))
        BACKEND_UP.labels(backend=backend_id).set(0)
        return out

    @app.post("/gateway/backends/{backend_id}/crash")
    async def crash_backend(backend_id: str, body: CrashIn | None = None):
        # The gateway is not told the replica died; it must detect it from refused connections.
        d = disp()
        if backend_id not in d.backends:
            raise HTTPException(404, f"Unknown backend {backend_id}")
        down = body.down_seconds if body else 15
        if not 0 <= down <= 300:
            raise HTTPException(400, "down_seconds must be between 0 and 300")
        if not any(b.healthy for k, b in d.backends.items() if k != backend_id):
            raise HTTPException(409, "Refusing to crash the last healthy backend")
        url = d.backends[backend_id].config.url + "/admin/crash"
        try:
            r = await app.state.client.post(url, params={"down_seconds": down}, timeout=5)
        except httpx.HTTPError as e:
            raise HTTPException(502, f"backend {backend_id} unreachable: {e}")
        if r.status_code != 200:
            raise HTTPException(r.status_code, r.json().get("detail", r.text) if r.content else r.text)
        d._event("backend_crash_requested", backend_id=backend_id, down_seconds=down)
        return {"backend_id": backend_id, "down_seconds": down, "backend_answer": r.json()}

    @app.get("/gateway/metrics")
    def metrics():
        d = disp()
        BACKLOG.set(d.backlog_count())
        for b in d.backends.values():
            INFLIGHT.labels(backend=b.backend_id).set(b.inflight)
            BACKEND_UP.labels(backend=b.backend_id).set(1 if b.healthy else 0)
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
                   include_in_schema=False)
    async def proxy(full_path: str, request: Request):
        d = disp()
        path = "/" + full_path
        route = route_key(request.method, path)
        rec = d.submit(request.method, path, route)
        body = await request.body()
        fwd_headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP}
        client_ip = request.client.host if request.client else ""
        prior = request.headers.get("x-forwarded-for")
        fwd_headers["x-forwarded-for"] = f"{prior}, {client_ip}" if prior else client_ip

        for attempt in range(settings.max_attempts):
            try:
                backend = await d.acquire(rec)
            except QueueTimeout as e:
                QUEUE_TIMEOUTS.inc()
                return _gateway_error(503, str(e), d, rec)
            except NoBackendAvailable as e:
                return _gateway_error(503, str(e), d, rec)
            url = backend.config.url + path
            if request.url.query:
                url += "?" + request.url.query
            try:
                upstream = await app.state.client.request(request.method, url, headers=fwd_headers, content=body)
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError) as e:
                # The request never reached the backend (or the connection dropped before any
                # response): safe to re-dispatch. Mark the backend down until a probe succeeds.
                logger.warning("backend %s unreachable (%s); re-dispatching task %s", backend.backend_id, e, rec.task_id)
                d.release(rec, backend, None, False, retry=True)
                d.report_probe(backend.backend_id, False)
                d.set_health(backend.backend_id, False)
                RETRIES.inc()
                continue
            except httpx.HTTPError as e:
                d.release(rec, backend, 502, False)
                REQUESTS_TOTAL.labels(backend.backend_id, route, "5xx").inc()
                return _gateway_error(502, f"backend {backend.backend_id} error: {e}", d, rec)
            return _finish(d, rec, backend, upstream, route)
        return _gateway_error(503, "no backend accepted the request", d, rec)

    def _finish(d: Dispatcher, rec: RequestRecord, backend: Backend, upstream: httpx.Response, route: str) -> Response:
        ok = upstream.status_code < 500
        d.release(rec, backend, upstream.status_code, ok)
        REQUESTS_TOTAL.labels(backend.backend_id, route, _status_class(upstream.status_code)).inc()
        if rec.wait_seconds is not None:
            QUEUE_WAIT.labels(backend.backend_id).observe(rec.wait_seconds)
        if rec.service_seconds is not None:
            SERVICE_TIME.labels(backend.backend_id).observe(rec.service_seconds)
        headers = {k: v for k, v in upstream.headers.items() if k.lower() not in HOP_BY_HOP
                   and k.lower() != "content-encoding"}
        headers.update(_trace_headers(d, rec))
        return Response(content=upstream.content, status_code=upstream.status_code, headers=headers)

    def _trace_headers(d: Dispatcher, rec: RequestRecord) -> dict[str, str]:
        h = {"x-cloudpulse-algorithm": d.algorithm, "x-cloudpulse-task-id": str(rec.task_id),
             "x-cloudpulse-attempts": str(rec.attempts)}
        if rec.backend_id:
            h["x-cloudpulse-backend"] = rec.backend_id
        if rec.wait_seconds is not None:
            h["x-cloudpulse-wait-ms"] = f"{rec.wait_seconds * 1000:.2f}"
        if rec.service_seconds is not None:
            h["x-cloudpulse-service-ms"] = f"{rec.service_seconds * 1000:.2f}"
        return h

    def _gateway_error(status: int, detail: str, d: Dispatcher, rec: RequestRecord) -> Response:
        d.records.pop(rec.task_id, None)
        REQUESTS_TOTAL.labels("gateway", rec.route, _status_class(status)).inc()
        import json
        return Response(content=json.dumps({"detail": detail, "source": "scheduler-gateway"}), status_code=status,
                        media_type="application/json", headers=_trace_headers(d, rec))

    return app


async def _health_loop(app: FastAPI, settings: Settings) -> None:
    d: Dispatcher = app.state.dispatcher
    client: httpx.AsyncClient = app.state.client
    while True:
        for b in list(d.backends.values()):
            try:
                r = await client.get(b.config.url + "/api/health", timeout=settings.health_timeout)
                d.report_probe(b.backend_id, r.status_code == 200)
            except httpx.HTTPError:
                d.report_probe(b.backend_id, False)
        await asyncio.sleep(settings.health_interval)


app = create_app()

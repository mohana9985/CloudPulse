from __future__ import annotations

import asyncio
import random
import statistics
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

KINDS = ("home", "categories", "list", "filter", "detail", "search", "order")

MIXES: dict[str, dict[str, int]] = {
    "browse": {"home": 25, "categories": 10, "list": 20, "filter": 10, "detail": 35},
    # search-heavy (most expensive read queries)
    "search": {"search": 50, "filter": 25, "detail": 25},
    # browsing + searching + some checkouts (writes to the shared SQLite database)
    "shopping": {"home": 15, "list": 15, "filter": 10, "detail": 30, "search": 20, "order": 10},
    "mixed": {"home": 15, "categories": 5, "list": 15, "filter": 15, "detail": 30, "search": 15, "order": 5},
}

SEARCH_TERMS = ["headphones", "keyboard", "bottle", "book", "cloud", "python", "shoes", "watch", "chair",
                "pen", "yoga", "kettle", "linux", "monitor", "jacket"]
SORTS = ["name", "price_asc", "price_desc", "newest"]
NAMES = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Ananya", "Vikram", "Isha"]
CITIES = ["Pilani", "Jaipur", "Hyderabad", "Goa", "Pune", "Chennai", "Delhi", "Mumbai"]

FALLBACK_CATALOG = {"product_ids": list(range(1, 25)), "categories": ["Books", "Electronics"]}


@dataclass(frozen=True)
class RequestSpec:
    seq: int
    offset: float          # seconds after run start
    kind: str
    method: str
    path: str
    body: dict | None = None


@dataclass
class RunConfig:
    num_requests: int
    rate: float            # mean arrival rate, requests per second (Poisson arrivals)
    mix: str = "mixed"
    seed: int = 42
    max_concurrency: int = 64
    label: str = ""

    def validate(self) -> None:
        if not 1 <= self.num_requests <= 100_000:
            raise ValueError("num_requests must be between 1 and 100000")
        if not 0.1 <= self.rate <= 1000:
            raise ValueError("rate must be between 0.1 and 1000 requests/second")
        if self.mix not in MIXES:
            raise ValueError(f"mix must be one of {sorted(MIXES)}")
        if not 1 <= self.max_concurrency <= 500:
            raise ValueError("max_concurrency must be between 1 and 500")


# Same (num_requests, rate, mix, seed, catalog) -> identical requests at identical offsets,
# so runs with different algorithms are comparable.
def build_plan(cfg: RunConfig, catalog: dict | None = None) -> list[RequestSpec]:
    cfg.validate()
    catalog = catalog or FALLBACK_CATALOG
    pids = list(catalog.get("product_ids") or FALLBACK_CATALOG["product_ids"])
    cats = list(catalog.get("categories") or FALLBACK_CATALOG["categories"])
    rng = random.Random(cfg.seed)
    kinds = list(MIXES[cfg.mix])
    weights = [MIXES[cfg.mix][k] for k in kinds]
    plan, t = [], 0.0
    for i in range(cfg.num_requests):
        if i:
            t += rng.expovariate(cfg.rate)
        kind = rng.choices(kinds, weights)[0]
        method, body = "GET", None
        if kind == "home":
            path = "/api/products?sort=newest&page_size=8"
        elif kind == "categories":
            path = "/api/categories"
        elif kind == "list":
            path = "/api/products"
        elif kind == "filter":
            path = f"/api/products?category={rng.choice(cats).replace(' ', '%20').replace('&', '%26')}" \
                   f"&sort={rng.choice(SORTS)}"
        elif kind == "detail":
            path = f"/api/products/{rng.choice(pids)}"
        elif kind == "search":
            path = f"/api/products/search?q={rng.choice(SEARCH_TERMS)}"
        else:
            method, path = "POST", "/api/orders"
            name = rng.choice(NAMES)
            chosen = rng.sample(pids, min(len(pids), rng.randint(1, 3)))
            body = {
                "customer_name": f"{name} Loadtest",
                "email": f"{name.lower()}.{rng.randint(1, 99999)}@example.com",
                "address": f"{rng.randint(1, 999)} Demo Road, {rng.choice(CITIES)}, India",
                "items": [{"product_id": p, "quantity": rng.randint(1, 2)} for p in chosen],
            }
        plan.append(RequestSpec(i, round(t, 4), kind, method, path, body))
    return plan


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))]


# 409 on an order = out of stock: a valid answer from the store, counted as ok.
def classify(status: int | None, kind: str) -> str:
    if status is None:
        return "network_error"
    if status < 400 or (kind == "order" and status == 409):
        return "ok"
    if status < 500:
        return "client_error"
    return "server_error"


@dataclass
class RequestResult:
    seq: int
    kind: str
    method: str
    path: str
    started: float          # seconds after run start
    latency_ms: float
    status: int | None
    outcome: str
    backend: str | None = None
    algorithm: str | None = None
    gateway_wait_ms: float | None = None
    gateway_service_ms: float | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def _float(v: str | None) -> float | None:
    try:
        return None if v is None else float(v)
    except ValueError:
        return None


@dataclass
class Run:
    run_id: int
    config: RunConfig
    plan_size: int
    started_unix: float = field(default_factory=time.time)
    started_mono: float = field(default_factory=time.monotonic)
    finished_mono: float | None = None
    state: str = "running"          # running / completed / stopped / failed
    sent: int = 0
    inflight: int = 0
    stop_requested: bool = False
    error: str | None = None
    results: list[RequestResult] = field(default_factory=list)
    recent: deque = field(default_factory=lambda: deque(maxlen=300))

    def record(self, r: RequestResult) -> None:
        self.results.append(r)
        self.recent.append(r)

    def elapsed(self) -> float:
        end = self.finished_mono if self.finished_mono is not None else time.monotonic()
        return max(0.0, end - self.started_mono)

    def summary(self) -> dict[str, Any]:
        res = self.results
        lat = [r.latency_ms for r in res]
        outcomes = Counter(r.outcome for r in res)
        backends = Counter(r.backend for r in res if r.backend)
        algos = Counter(r.algorithm for r in res if r.algorithm)
        done_backend = sum(backends.values())
        by_kind = {}
        for kind in KINDS:
            kl = [r.latency_ms for r in res if r.kind == kind]
            if kl:
                by_kind[kind] = {
                    "requests": len(kl),
                    "errors": sum(1 for r in res if r.kind == kind and r.outcome != "ok"),
                    "avg_ms": round(statistics.fmean(kl), 2),
                    "p95_ms": round(percentile(kl, 0.95), 2),
                }
        elapsed = self.elapsed()
        waits = [r.gateway_wait_ms for r in res if r.gateway_wait_ms is not None]
        services = [r.gateway_service_ms for r in res if r.gateway_service_ms is not None]
        cfg = self.config
        return {
            "run_id": self.run_id,
            "label": cfg.label,
            "state": self.state,
            "algorithm": algos.most_common(1)[0][0] if algos else None,
            "mix": cfg.mix,
            "seed": cfg.seed,
            "target_rate_rps": cfg.rate,
            "max_concurrency": cfg.max_concurrency,
            "planned": self.plan_size,
            "sent": self.sent,
            "completed": len(res),
            "inflight": self.inflight,
            "ok": outcomes.get("ok", 0),
            "client_errors": outcomes.get("client_error", 0),
            "server_errors": outcomes.get("server_error", 0),
            "network_errors": outcomes.get("network_error", 0),
            "error_rate_pct": round(100 * (len(res) - outcomes.get("ok", 0)) / len(res), 2) if res else 0.0,
            "started_unix": round(self.started_unix, 3),
            "elapsed_seconds": round(elapsed, 2),
            "achieved_rps": round(len(res) / elapsed, 2) if elapsed > 0 and res else 0.0,
            "avg_ms": round(statistics.fmean(lat), 2) if lat else None,
            "p50_ms": None if not lat else round(percentile(lat, 0.50), 2),
            "p95_ms": None if not lat else round(percentile(lat, 0.95), 2),
            "p99_ms": None if not lat else round(percentile(lat, 0.99), 2),
            "max_ms": round(max(lat), 2) if lat else None,
            "avg_gateway_wait_ms": round(statistics.fmean(waits), 2) if waits else None,
            "avg_backend_service_ms": round(statistics.fmean(services), 2) if services else None,
            "requests_per_backend": dict(sorted(backends.items())),
            "share_per_backend": {k: round(100 * v / done_backend, 1) for k, v in sorted(backends.items())},
            "by_kind": by_kind,
            "error": self.error,
        }


Observer = Callable[[RequestResult], None]


async def send_one(client: httpx.AsyncClient, base_url: str, spec: RequestSpec, run: Run) -> RequestResult:
    t0 = time.monotonic()
    started = t0 - run.started_mono
    status, headers, err = None, {}, None
    try:
        resp = await client.request(spec.method, base_url + spec.path, json=spec.body)
        status, headers = resp.status_code, resp.headers
    except httpx.HTTPError as e:
        err = f"{type(e).__name__}: {e}"[:200]
    latency = (time.monotonic() - t0) * 1000
    return RequestResult(
        seq=spec.seq, kind=spec.kind, method=spec.method, path=spec.path, started=round(started, 4),
        latency_ms=round(latency, 2), status=status, outcome=classify(status, spec.kind),
        backend=headers.get("x-cloudpulse-backend"), algorithm=headers.get("x-cloudpulse-algorithm"),
        gateway_wait_ms=_float(headers.get("x-cloudpulse-wait-ms")),
        gateway_service_ms=_float(headers.get("x-cloudpulse-service-ms")), error=err,
    )


# Open loop: request i is sent at its planned offset; with max_concurrency in flight,
# later arrivals wait for a free slot.
async def execute(run: Run, plan: list[RequestSpec], client: httpx.AsyncClient, base_url: str,
                  observer: Observer | None = None) -> None:
    sem = asyncio.Semaphore(run.config.max_concurrency)
    pending: set[asyncio.Task] = set()

    async def one(spec: RequestSpec) -> None:
        try:
            r = await send_one(client, base_url, spec, run)
            run.record(r)
            if observer:
                observer(r)
        finally:
            run.inflight -= 1
            sem.release()

    try:
        for spec in plan:
            if run.stop_requested:
                break
            delay = run.started_mono + spec.offset - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            await sem.acquire()
            if run.stop_requested:
                sem.release()
                break
            run.sent += 1
            run.inflight += 1
            task = asyncio.create_task(one(spec))
            pending.add(task)
            task.add_done_callback(pending.discard)
        if pending:
            await asyncio.gather(*list(pending), return_exceptions=True)
        run.state = "stopped" if run.stop_requested else "completed"
    except asyncio.CancelledError:
        run.state = "stopped"
        for t in list(pending):
            t.cancel()
        raise
    except Exception as e:  # pragma: no cover - defensive
        run.state, run.error = "failed", str(e)
    finally:
        run.finished_mono = time.monotonic()


async def fetch_catalog(client: httpx.AsyncClient, base_url: str) -> dict:
    try:
        items = (await client.get(base_url + "/api/products?page_size=100")).json()["items"]
        cats = [c["name"] for c in (await client.get(base_url + "/api/categories")).json()]
        catalog = {"product_ids": [p["id"] for p in items], "categories": cats}
        if catalog["product_ids"] and catalog["categories"]:
            return catalog
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        pass
    return dict(FALLBACK_CATALOG)

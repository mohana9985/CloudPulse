import asyncio
import json

import httpx
import pytest

from gateway.app import create_app


class FakeBackends:

    def __init__(self, delay: float = 0.0):
        self.calls: list[tuple[str, str]] = []      # (backend host, path)
        self.down: set[str] = set()
        self.delay = delay
        self.crashed: list[tuple[str, str]] = []

    async def handler(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host in self.down:
            raise httpx.ConnectError("connection refused", request=request)
        path = request.url.path
        if path == "/api/health":
            return httpx.Response(200, json={"status": "ok", "host": host})
        self.calls.append((host, path))
        if self.delay:
            await asyncio.sleep(self.delay)
        if path.startswith("/api/products"):
            return httpx.Response(200, json={"items": [], "host": host}, headers={"x-backend-host": host})
        if path == "/api/orders" and request.method == "POST":
            return httpx.Response(201, json={"id": 1, "echo": json.loads(request.content), "host": host})
        if path == "/admin/crash":
            if host == "b3":
                return httpx.Response(403, json={"detail": "Failure demo disabled"})
            self.crashed.append((host, request.url.params.get("down_seconds")))
            return httpx.Response(200, json={"crashing": True})
        if path == "/api/boom":
            return httpx.Response(500, json={"detail": "boom"})
        return httpx.Response(404, json={"detail": "not found"})


@pytest.fixture
async def gateway(settings):
    fakes = FakeBackends()
    app = create_app(settings, transport=httpx.MockTransport(fakes.handler))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as client:
            yield client, fakes, app


async def test_proxies_and_tags_response(gateway):
    client, fakes, _ = gateway
    r = await client.get("/api/products?page=1")
    assert r.status_code == 200
    assert r.headers["x-cloudpulse-backend"] == "B1"
    assert r.headers["x-cloudpulse-algorithm"] == "least_loaded"
    assert "x-cloudpulse-service-ms" in r.headers
    assert r.json()["host"] == "b1"
    assert fakes.calls == [("b1", "/api/products")]


async def test_post_body_forwarded(gateway):
    client, fakes, _ = gateway
    r = await client.post("/api/orders", json={"customer_name": "x"})
    assert r.status_code == 201 and r.json()["echo"] == {"customer_name": "x"}


async def test_round_robin_spreads_sequential_requests(gateway):
    client, fakes, _ = gateway
    r = await client.post("/gateway/algorithm", json={"algorithm": "round_robin"})
    assert r.status_code == 200 and r.json()["active"] == "round_robin"
    hosts = [(await client.get("/api/products")).headers["x-cloudpulse-backend"] for _ in range(6)]
    assert hosts == ["B1", "B2", "B3", "B1", "B2", "B3"]


async def test_backend_5xx_counted_as_error_not_retried(gateway):
    client, fakes, _ = gateway
    r = await client.get("/api/boom")
    assert r.status_code == 500
    stats = (await client.get("/gateway/stats")).json()
    assert stats["counters"]["errors"] == 1 and stats["counters"]["retries"] == 0


async def test_connection_failure_redispatches_to_another_backend(gateway):
    client, fakes, _ = gateway
    await client.post("/gateway/algorithm", json={"algorithm": "round_robin"})
    await client.get("/api/products")                     # B1
    fakes.down.add("b2")
    r = await client.get("/api/products")                 # B2 refused -> re-dispatched
    assert r.status_code == 200 and r.headers["x-cloudpulse-backend"] != "B2"
    assert int(r.headers["x-cloudpulse-attempts"]) == 2
    stats = (await client.get("/gateway/stats")).json()
    assert stats["counters"]["retries"] == 1
    b2 = next(b for b in stats["backends"] if b["backend_id"] == "B2")
    assert b2["healthy"] is False
    events = (await client.get("/gateway/events")).json()["events"]
    assert any(e["type"] == "backend_unavailable" and e["backend_id"] == "B2" for e in events)
    fakes.down.discard("b2")
    for _ in range(20):                                   # health loop (0.2 s) brings B2 back
        await asyncio.sleep(0.1)
        stats = (await client.get("/gateway/stats")).json()
        if next(b for b in stats["backends"] if b["backend_id"] == "B2")["healthy"]:
            break
    assert next(b for b in stats["backends"] if b["backend_id"] == "B2")["healthy"] is True


async def test_control_endpoints(gateway):
    client, _, _ = gateway
    assert (await client.get("/gateway/health")).json()["status"] == "ok"
    await client.get("/api/products")
    recent = (await client.get("/gateway/recent")).json()["items"]
    assert recent and recent[0]["route"] == "GET /api/products"
    r = await client.post("/gateway/reset", json={"label": "t"})
    assert r.json()["archived_run"]["completed"] == 1
    assert (await client.get("/gateway/runs")).json()["runs"][0]["label"] == "t"
    m = await client.get("/gateway/metrics")
    assert m.status_code == 200 and b"gateway_requests_total" in m.content
    assert (await client.post("/gateway/algorithm", json={"algorithm": "bogus"})).status_code == 400


async def test_concurrent_requests_distribute_and_queue(settings):
    fakes = FakeBackends(delay=0.05)
    app = create_app(settings, transport=httpx.MockTransport(fakes.handler))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://gateway") as client:
            await client.post("/gateway/algorithm", json={"algorithm": "least_loaded"})
            rs = await asyncio.gather(*(client.get("/api/products") for _ in range(12)))
            assert all(r.status_code == 200 for r in rs)
            served = {r.headers["x-cloudpulse-backend"] for r in rs}
            assert served == {"B1", "B2", "B3"}
            waited = [float(r.headers["x-cloudpulse-wait-ms"]) for r in rs]
            assert max(waited) > 10          # only 4 slots: some requests had to queue
            stats = (await client.get("/gateway/stats")).json()
            assert stats["counters"]["completed"] == 12 and stats["inflight"] == 0


async def test_simulated_outage_removes_backend_then_recovers(gateway):
    client, fakes, _ = gateway
    await client.post("/gateway/algorithm", json={"algorithm": "round_robin"})
    r = await client.post("/gateway/backends/B2/outage", json={"seconds": 1})
    assert r.status_code == 200 and r.json() == {"backend_id": "B2", "seconds": 1}
    hosts = [(await client.get("/api/products")).headers["x-cloudpulse-backend"] for _ in range(6)]
    assert "B2" not in hosts
    await asyncio.sleep(0.5)                              # healthy probes are ignored during the outage
    b2 = next(b for b in (await client.get("/gateway/backends")).json()["backends"] if b["backend_id"] == "B2")
    assert b2["healthy"] is False and b2["simulated_outage_remaining_s"] > 0
    for _ in range(30):                                   # after it expires the health loop restores it
        await asyncio.sleep(0.1)
        stats = (await client.get("/gateway/stats")).json()
        if next(b for b in stats["backends"] if b["backend_id"] == "B2")["healthy"]:
            break
    else:
        raise AssertionError("B2 did not recover")
    types = [e["type"] for e in (await client.get("/gateway/events")).json()["events"]]
    assert "backend_outage_simulated" in types and "backend_recovered" in types


async def test_simulated_outage_validation(gateway):
    client, _, _ = gateway
    assert (await client.post("/gateway/backends/B9/outage", json={"seconds": 5})).status_code == 404
    assert (await client.post("/gateway/backends/B1/outage", json={"seconds": 0})).status_code == 400
    assert (await client.post("/gateway/backends/B1/outage", json={"seconds": 5})).status_code == 200
    assert (await client.post("/gateway/backends/B2/outage", json={"seconds": 5})).status_code == 200
    r = await client.post("/gateway/backends/B3/outage", json={"seconds": 5})
    assert r.status_code == 409                           # never take down the last healthy replica


async def test_crash_endpoint_calls_backend_and_logs_event(gateway):
    client, fakes, _ = gateway
    r = await client.post("/gateway/backends/B2/crash", json={"down_seconds": 12})
    assert r.status_code == 200 and r.json()["down_seconds"] == 12
    assert fakes.crashed == [("b2", "12.0")]
    events = (await client.get("/gateway/events")).json()["events"]
    assert any(e["type"] == "backend_crash_requested" and e["backend_id"] == "B2" for e in events)
    # the gateway does not mark the replica down itself: detection must come from real failures
    b2 = next(b for b in (await client.get("/gateway/backends")).json()["backends"] if b["backend_id"] == "B2")
    assert b2["healthy"] is True


async def test_crash_endpoint_errors(gateway):
    client, fakes, _ = gateway
    assert (await client.post("/gateway/backends/B9/crash", json={})).status_code == 404
    assert (await client.post("/gateway/backends/B1/crash", json={"down_seconds": 999})).status_code == 400
    assert (await client.post("/gateway/backends/B3/crash", json={})).status_code == 403   # disabled on backend
    fakes.down.add("b1")
    assert (await client.post("/gateway/backends/B1/crash", json={})).status_code == 502

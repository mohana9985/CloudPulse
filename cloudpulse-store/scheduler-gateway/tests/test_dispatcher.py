import asyncio

import pytest

from gateway.config import route_key
from gateway.dispatcher import ConflictError, Dispatcher, QueueTimeout


def test_route_key_normalises_ids():
    assert route_key("get", "/api/products/12") == "GET /api/products/{id}"
    assert route_key("GET", "/api/products/search?q=x") == "GET /api/products/search"
    assert route_key("POST", "/api/orders/") == "POST /api/orders"
    assert route_key("GET", "/api/orders/7/") == "GET /api/orders/{id}"


async def _route(d: Dispatcher, route="GET /api/products", status=200, service=0.0):
    rec = d.submit("GET", "/api/products", route)
    backend = await d.acquire(rec)
    if service:
        await asyncio.sleep(service)
    d.release(rec, backend, status, status < 500)
    return backend.backend_id


async def test_round_robin_cycles_backends(settings):
    d = Dispatcher(settings)
    d.set_algorithm("round_robin")
    served = [await _route(d) for _ in range(6)]
    assert served == ["B1", "B2", "B3", "B1", "B2", "B3"]


async def test_weighted_round_robin_follows_weights(settings):
    d = Dispatcher(settings)
    d.set_algorithm("weighted_round_robin")
    served = [await _route(d) for _ in range(10)]
    assert served.count("B1") == 5 and served.count("B2") == 3 and served.count("B3") == 2


async def test_least_loaded_prefers_backend_with_least_estimated_work(settings):
    d = Dispatcher(settings)
    d.set_algorithm("least_loaded")
    d.estimates["GET /api/products"] = 0.1
    r1 = d.submit("GET", "/api/products", "GET /api/products")
    b1 = await d.acquire(r1)                      # all idle -> B1 (config order on ties)
    assert b1.backend_id == "B1"
    r2 = d.submit("GET", "/api/products", "GET /api/products")
    b2 = await d.acquire(r2)                      # B1 now carries 0.1/1.0 = 0.1 load; B2 idle -> B2
    assert b2.backend_id == "B2"
    r3 = d.submit("GET", "/api/products", "GET /api/products")
    b3 = await d.acquire(r3)                      # loads B1=0.1, B2=0.167, B3=0 -> B3
    assert b3.backend_id == "B3"
    r4 = d.submit("GET", "/api/products", "GET /api/products")
    b4 = await d.acquire(r4)                      # loads B1=0.1, B2=0.167, B3=0.25 -> B1 (has 2 slots)
    assert b4.backend_id == "B1"
    for rec, b in ((r1, b1), (r2, b2), (r3, b3), (r4, b4)):
        d.release(rec, b, 200, True)
    assert d.active_count() == 0


async def test_requests_wait_when_all_slots_busy_then_proceed(settings):
    d = Dispatcher(settings)
    d.set_algorithm("round_robin")
    held = []
    for _ in range(4):                            # slots: B1=2, B2=1, B3=1 -> 4 in flight
        rec = d.submit("GET", "/api/products", "GET /api/products")
        held.append((rec, await d.acquire(rec)))
    waiting = d.submit("GET", "/api/products", "GET /api/products")
    task = asyncio.create_task(d.acquire(waiting))
    await asyncio.sleep(0.05)
    assert not task.done() and d.backlog_count() == 1
    rec, b = held.pop()
    d.release(rec, b, 200, True)                  # frees a slot -> waiting request dispatched
    backend = await asyncio.wait_for(task, 1)
    assert backend.backend_id == b.backend_id
    d.release(waiting, backend, 200, True)
    for rec, b in held:
        d.release(rec, b, 200, True)


async def test_queue_timeout(settings):
    d = Dispatcher(settings)
    d.settings = settings.__class__(**{**settings.__dict__, "queue_timeout": 0.1})
    held = []
    for _ in range(4):
        rec = d.submit("GET", "/api/products", "GET /api/products")
        held.append((rec, await d.acquire(rec)))
    waiting = d.submit("GET", "/api/products", "GET /api/products")
    with pytest.raises(QueueTimeout):
        await d.acquire(waiting)
    assert d.counters["queue_timeouts"] == 1 and d.backlog_count() == 0
    for rec, b in held:
        d.release(rec, b, 200, True)


async def test_sjf_releases_short_request_before_long_one(settings):
    d = Dispatcher(settings)
    d.set_algorithm("shortest_job_first")
    d.estimates["POST /api/orders"] = 0.05
    d.estimates["GET /api/health"] = 0.002
    held = []
    for _ in range(4):                            # fill every slot
        rec = d.submit("GET", "/api/products", "GET /api/products")
        held.append((rec, await d.acquire(rec)))
    long_rec = d.submit("POST", "/api/orders", "POST /api/orders")
    short_rec = d.submit("GET", "/api/health", "GET /api/health")
    long_task = asyncio.create_task(d.acquire(long_rec))
    short_task = asyncio.create_task(d.acquire(short_rec))
    await asyncio.sleep(0.02)
    assert d.backlog_count() == 2
    rec, b = held.pop(0)
    d.release(rec, b, 200, True)                  # one slot frees: SJF must pick the health check
    await asyncio.sleep(0.02)
    assert short_task.done() and not long_task.done()
    rec, b = held.pop(0)
    d.release(rec, b, 200, True)
    await asyncio.wait_for(long_task, 1)
    for t, r in ((short_task, short_rec), (long_task, long_rec)):
        d.release(r, t.result(), 200, True)
    for rec, b in held:
        d.release(rec, b, 200, True)


async def test_fcfs_keeps_arrival_order(settings):
    d = Dispatcher(settings)
    d.set_algorithm("fcfs_baseline")
    d.estimates["POST /api/orders"] = 0.05
    d.estimates["GET /api/health"] = 0.002
    held = []
    for _ in range(4):
        rec = d.submit("GET", "/api/products", "GET /api/products")
        held.append((rec, await d.acquire(rec)))
    long_rec = d.submit("POST", "/api/orders", "POST /api/orders")
    short_rec = d.submit("GET", "/api/health", "GET /api/health")
    long_task = asyncio.create_task(d.acquire(long_rec))
    short_task = asyncio.create_task(d.acquire(short_rec))
    await asyncio.sleep(0.02)
    rec, b = held.pop(0)
    d.release(rec, b, 200, True)
    await asyncio.sleep(0.02)
    assert long_task.done() and not short_task.done()
    rec, b = held.pop(0)
    d.release(rec, b, 200, True)
    await asyncio.wait_for(short_task, 1)
    for t, r in ((short_task, short_rec), (long_task, long_rec)):
        d.release(r, t.result(), 200, True)
    for rec, b in held:
        d.release(rec, b, 200, True)


async def test_unhealthy_backend_is_skipped_and_rejoins(settings):
    d = Dispatcher(settings)
    d.set_algorithm("round_robin")
    d.set_health("B2", False)
    served = [await _route(d) for _ in range(4)]
    assert "B2" not in served and set(served) == {"B1", "B3"}
    d.set_health("B2", True)
    served = [await _route(d) for _ in range(3)]
    assert "B2" in served
    kinds = [e["type"] for e in d.events]
    assert "backend_unavailable" in kinds and "backend_recovered" in kinds


async def test_estimates_learn_from_observed_service_time(settings):
    d = Dispatcher(settings)
    before = d.estimate_for("GET /api/products")
    await _route(d, service=0.05)
    after = d.estimate_for("GET /api/products")
    assert after > before


async def test_cannot_change_algorithm_with_backlog(settings):
    d = Dispatcher(settings)
    d.set_algorithm("round_robin")
    held = []
    for _ in range(4):
        rec = d.submit("GET", "/api/products", "GET /api/products")
        held.append((rec, await d.acquire(rec)))
    waiting = d.submit("GET", "/api/products", "GET /api/products")
    task = asyncio.create_task(d.acquire(waiting))
    await asyncio.sleep(0.02)
    with pytest.raises(ConflictError):
        d.set_algorithm("least_loaded")
    with pytest.raises(ValueError):
        d.set_algorithm("nope")
    rec, b = held.pop()
    d.release(rec, b, 200, True)
    d.release(waiting, await task, 200, True)
    for rec, b in held:
        d.release(rec, b, 200, True)
    d.set_algorithm("least_loaded")
    assert d.algorithm == "least_loaded"


async def test_reset_archives_run(settings):
    d = Dispatcher(settings)
    for _ in range(5):
        await _route(d)
    summary = d.reset_run("demo")
    assert summary["completed"] == 5 and summary["label"] == "demo" and summary["algorithm"] == "least_loaded"
    assert sum(summary["completed_per_backend"].values()) == 5
    assert d.run_id == 2 and d.runs[-1] is summary
    assert d.stats()["run"]["completed"] == 0


async def test_stats_shape(settings):
    d = Dispatcher(settings)
    await _route(d)
    s = d.stats()
    assert s["algorithm"] == "least_loaded" and s["dispatch_mode"] == "per_worker_queue"
    assert {b["backend_id"] for b in s["backends"]} == {"B1", "B2", "B3"}
    assert s["counters"]["completed"] == 1 and s["inflight"] == 0 and s["backlog"] == 0
    assert "GET /api/products" in s["route_estimates_ms"]
    assert d.recent[-1]["backend_id"] == "B1"

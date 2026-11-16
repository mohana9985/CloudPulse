import time
from collections import Counter

import httpx
import pytest
from fastapi.testclient import TestClient

from loadgen.app import create_app
from loadgen.engine import MIXES, Run, RunConfig, build_plan, classify, execute, percentile

CATALOG = {"product_ids": [1, 2, 3, 4, 5], "categories": ["Books", "Home & Kitchen"]}


def fake_store(fail_backend: str | None = None, delay: float = 0.0):
    counter = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if delay:
            time.sleep(delay)
        counter["n"] += 1
        backend = ["B1", "B2", "B3"][counter["n"] % 3]
        headers = {"x-cloudpulse-backend": backend, "x-cloudpulse-algorithm": "least_loaded",
                   "x-cloudpulse-wait-ms": "1.50", "x-cloudpulse-service-ms": "12.00"}
        path = request.url.path
        if backend == fail_backend:
            return httpx.Response(502, json={"detail": "boom"}, headers=headers)
        if path == "/api/products" and request.url.params.get("page_size") == "100":
            return httpx.Response(200, json={"items": [{"id": i} for i in CATALOG["product_ids"]]})
        if path == "/api/categories":
            return httpx.Response(200, json=[{"name": c} for c in CATALOG["categories"]])
        if path == "/api/orders":
            return httpx.Response(201, json={"id": 1}, headers=headers)
        return httpx.Response(200, json={}, headers=headers)

    return httpx.MockTransport(handler)


def test_plan_is_deterministic_for_same_seed():
    cfg = RunConfig(200, 50, "mixed", 7)
    assert build_plan(cfg, CATALOG) == build_plan(cfg, CATALOG)
    assert build_plan(cfg, CATALOG) != build_plan(RunConfig(200, 50, "mixed", 8), CATALOG)


def test_plan_offsets_follow_rate():
    plan = build_plan(RunConfig(2000, 100, "browse", 1), CATALOG)
    assert plan[0].offset == 0
    assert all(b.offset >= a.offset for a, b in zip(plan, plan[1:]))
    assert 15 < plan[-1].offset < 25        # 2000 requests at ~100/s


def test_plan_respects_mix_and_catalog():
    plan = build_plan(RunConfig(3000, 100, "search", 3), CATALOG)
    kinds = Counter(p.kind for p in plan)
    assert set(kinds) <= set(MIXES["search"])
    assert abs(kinds["search"] / 3000 - 0.5) < 0.05
    for p in plan:
        if p.kind == "detail":
            assert int(p.path.rsplit("/", 1)[1]) in CATALOG["product_ids"]
    assert all(p.method == "GET" for p in plan)


def test_order_requests_have_valid_payload():
    plan = build_plan(RunConfig(500, 100, "shopping", 5), CATALOG)
    orders = [p for p in plan if p.kind == "order"]
    assert orders
    for o in orders:
        assert o.method == "POST" and o.path == "/api/orders"
        assert {"customer_name", "email", "address", "items"} <= set(o.body)
        assert all(i["product_id"] in CATALOG["product_ids"] for i in o.body["items"])


def test_filter_path_encodes_category():
    plan = build_plan(RunConfig(500, 100, "browse", 2), CATALOG)
    paths = [p.path for p in plan if p.kind == "filter"]
    assert any("Home%20%26%20Kitchen" in p for p in paths)


@pytest.mark.parametrize("cfg", [RunConfig(0, 1), RunConfig(1, 0), RunConfig(1, 1, "nope"),
                                 RunConfig(1, 1, "mixed", 1, 0)])
def test_invalid_config_rejected(cfg):
    with pytest.raises(ValueError):
        cfg.validate()


def test_classify_and_percentile():
    assert classify(200, "detail") == "ok"
    assert classify(409, "order") == "ok"
    assert classify(409, "detail") == "client_error"
    assert classify(503, "detail") == "server_error"
    assert classify(None, "home") == "network_error"
    assert percentile([], 0.5) is None
    assert percentile([1, 2, 3, 4, 5], 0.5) == 3
    assert percentile([1, 2, 3, 4, 100], 0.99) == 100


async def test_execute_records_backend_headers():
    cfg = RunConfig(30, 1000, "mixed", 1)
    plan = build_plan(cfg, CATALOG)
    run = Run(1, cfg, len(plan))
    async with httpx.AsyncClient(transport=fake_store()) as client:
        await execute(run, plan, client, "http://store")
    s = run.summary()
    assert s["state"] == "completed" and s["completed"] == 30 and s["ok"] == 30
    assert s["algorithm"] == "least_loaded"
    assert set(s["requests_per_backend"]) == {"B1", "B2", "B3"}
    assert abs(sum(s["share_per_backend"].values()) - 100) < 0.5
    assert s["avg_gateway_wait_ms"] == 1.5 and s["avg_backend_service_ms"] == 12.0
    assert run.inflight == 0


async def test_execute_counts_server_errors():
    cfg = RunConfig(30, 1000, "browse", 1)
    plan = build_plan(cfg, CATALOG)
    run = Run(1, cfg, len(plan))
    async with httpx.AsyncClient(transport=fake_store(fail_backend="B2")) as client:
        await execute(run, plan, client, "http://store")
    s = run.summary()
    assert s["server_errors"] == 10 and s["ok"] == 20
    assert s["error_rate_pct"] == pytest.approx(33.33, abs=0.01)


async def test_execute_network_error():
    def boom(request):
        raise httpx.ConnectError("refused")

    cfg = RunConfig(5, 1000, "browse", 1)
    plan = build_plan(cfg, CATALOG)
    run = Run(1, cfg, len(plan))
    async with httpx.AsyncClient(transport=httpx.MockTransport(boom)) as client:
        await execute(run, plan, client, "http://store")
    assert run.summary()["network_errors"] == 5
    assert run.results[0].error.startswith("ConnectError")


async def test_stop_request_halts_run():
    cfg = RunConfig(1000, 10, "browse", 1)          # would take ~100 s
    plan = build_plan(cfg, CATALOG)
    run = Run(1, cfg, len(plan))
    run.stop_requested = True
    async with httpx.AsyncClient(transport=fake_store()) as client:
        await execute(run, plan, client, "http://store")
    assert run.state == "stopped" and run.sent == 0


def wait_done(c: TestClient, timeout: float = 10.0) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        s = c.get("/loadgen/status").json()
        if not s["running"]:
            return s
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_api_full_run():
    app = create_app("http://store", transport=fake_store())
    with TestClient(app) as c:
        assert c.get("/loadgen/health").json()["status"] == "ok"
        assert "mixed" in c.get("/loadgen/config").json()["mixes"]
        r = c.post("/loadgen/start", json={"num_requests": 40, "rate": 500, "mix": "shopping", "seed": 3})
        assert r.status_code == 202 and r.json()["planned"] == 40 and r.json()["products_in_catalog"] == 5
        s = wait_done(c)["run"]
        assert s["completed"] == 40 and s["ok"] == 40 and s["state"] == "completed"
        recent = c.get("/loadgen/recent", params={"limit": 10}).json()["items"]
        assert len(recent) == 10 and recent[0]["backend"] in {"B1", "B2", "B3"}
        runs = c.get("/loadgen/runs").json()["runs"]
        assert len(runs) == 1 and runs[0]["algorithm"] == "least_loaded"
        m = c.get("/metrics").text
        assert "loadgen_requests_total" in m and 'outcome="ok"' in m and "loadgen_run_active 0.0" in m


def test_api_rejects_concurrent_runs_and_stops():
    app = create_app("http://store", transport=fake_store())
    with TestClient(app) as c:
        assert c.post("/loadgen/stop").status_code == 409
        assert c.post("/loadgen/start", json={"num_requests": 500, "rate": 5}).status_code == 202
        assert c.post("/loadgen/start", json={"num_requests": 5, "rate": 5}).status_code == 409
        assert c.post("/loadgen/stop").status_code == 200
        s = wait_done(c)["run"]
        assert s["state"] == "stopped" and s["completed"] < 500


def test_api_validation():
    app = create_app("http://store", transport=fake_store())
    with TestClient(app) as c:
        assert c.post("/loadgen/start", json={"num_requests": 0}).status_code == 422
        assert c.post("/loadgen/start", json={"mix": "bogus"}).status_code == 400
        assert c.get("/loadgen/status").json()["run"] is None
        assert c.get("/loadgen/recent").json()["items"] == []

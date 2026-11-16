import asyncio
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from live.coordinator.app import create_app
from live.coordinator.cluster import Cluster
from live.dashboard.api import CoordinatorClient, find_live_results, task_distribution
from live.tasks import run_task
from live.worker import metrics as wmetrics
from live.worker.agent import WorkerAgent
from live.worker.app import create_app as create_worker_app

WORKERS = [("W1", 1.0, 5), ("W2", 0.6, 3), ("W3", 0.4, 2)]


def coordinator(**kw):
    return create_app(cluster_factory=lambda: Cluster(**kw))


def register(client):
    for wid, cap, w in WORKERS:
        r = client.post("/workers/heartbeat", json={"worker_id": wid, "capacity": cap, "weight": w,
                                                    "metrics": {"cpu_percent_of_limit": 12.5,
                                                                "container_memory_mb": 40.0}})
        assert r.status_code == 200


def test_health_algorithms_and_metrics():
    c = TestClient(coordinator())
    assert c.get("/health").json()["status"] == "ok"
    algos = c.get("/scheduler/algorithms").json()
    names = {a["name"]: a["role"] for a in algos["algorithms"]}
    assert {n for n, r in names.items() if r == "primary"} == {
        "round_robin", "weighted_round_robin", "least_loaded", "shortest_job_first"}
    assert names["fcfs_baseline"] == "control"
    register(c)
    text = c.get("/metrics").text
    assert 'cloudpulse_worker_up{worker="W2"} 1.0' in text
    assert 'cloudpulse_worker_cpu_percent_of_limit{worker="W1"} 12.5' in text
    assert "cloudpulse_sched_submitted_total" in text


def test_submit_list_get_and_validation():
    c = TestClient(coordinator(algorithm="round_robin"))
    register(c)
    r = c.post("/tasks/submit", json={"task_type": "sha256_chain", "units": 1000})
    assert r.status_code == 201 and r.json()["task_ids"] == [1]
    r = c.post("/tasks/submit", json={"tasks": [{"task_type": "prime_count", "units": 500}] * 2})
    assert r.json()["task_ids"] == [2, 3]
    assert c.post("/tasks/submit", json={"task_type": "bogus", "units": 5}).status_code == 400
    assert c.post("/tasks/submit", json={"task_type": "prime_count", "units": 0}).status_code == 422
    listed = c.get("/tasks").json()
    assert listed["total"] == 3 and [t["worker_id"] for t in listed["tasks"]] == ["W1", "W2", "W3"]
    assert c.get("/tasks/2").json()["status"] == "queued"
    assert c.get("/tasks/99").status_code == 404


def test_algorithm_selection_and_conflicts():
    c = TestClient(coordinator())
    register(c)
    assert c.post("/scheduler/algorithm", json={"algorithm": "shortest_job_first"}).json()["active"] == \
        "shortest_job_first"
    assert c.post("/scheduler/algorithm", json={"algorithm": "nope"}).status_code == 400
    c.post("/tasks/submit", json={"task_type": "sha256_chain", "units": 1000})
    assert c.post("/scheduler/algorithm", json={"algorithm": "round_robin"}).status_code == 409
    assert c.post("/scheduler/reset", json={}).status_code == 409
    stats = c.get("/scheduler/stats").json()
    assert stats["algorithm"] == "shortest_job_first" and stats["backlog"] == 1


def test_workers_endpoints_and_poll_unknown():
    c = TestClient(coordinator())
    register(c)
    ws = c.get("/workers").json()["workers"]
    assert [w["worker_id"] for w in ws] == ["W1", "W2", "W3"] and all(w["status"] == "active" for w in ws)
    assert c.get("/workers/W1/metrics").json()["samples"][0]["container_memory_mb"] == 40.0
    assert c.get("/workers/W9").status_code == 404
    assert c.post("/workers/W9/poll", params={"wait": 0.1}).status_code == 404
    assert c.post("/workers/W1/poll", params={"wait": 0.05}).status_code == 204


def test_cgroup_parsing(tmp_path, monkeypatch):
    (tmp_path / "cpu.max").write_text("45000 100000\n")
    (tmp_path / "memory.current").write_text(str(64 * 2**20))
    (tmp_path / "memory.max").write_text("max")
    monkeypatch.setattr(wmetrics, "CGROUP", tmp_path)
    assert wmetrics.cgroup_cpu_limit_cores() == pytest.approx(0.45)
    assert wmetrics.cgroup_memory_mb() == (64.0, None)
    (tmp_path / "cpu.max").write_text("max 100000")
    assert wmetrics.cgroup_cpu_limit_cores() is None


def test_metrics_sampler_reports_real_values():
    s = wmetrics.MetricsSampler(cpu_limit_override=0.5).sample()
    assert s["cpu_limit_cores"] == 0.5 and s["process_rss_mb"] > 1
    assert 0 <= s["cpu_percent_of_limit"] <= 100 and 0 < s["host_memory_percent"] <= 100


def test_worker_api_and_chaos_guard(monkeypatch):
    agent = WorkerAgent("W7", "http://coordinator.invalid", capacity=0.6, weight=3)
    app = create_worker_app(agent_factory=lambda: agent)
    c = TestClient(app)  # no context manager: background loops not started
    assert c.get("/health").json() == {"status": "ok", "worker_id": "W7", "state": "idle",
                                       "last_heartbeat_ok_unix": None}
    assert c.get("/status").json()["capacity"] == 0.6
    assert "cpu_percent_of_limit" in c.get("/metrics").json()
    monkeypatch.delenv("ENABLE_CHAOS", raising=False)
    assert c.post("/admin/simulate-outage", params={"seconds": 5}).status_code == 403
    monkeypatch.setenv("ENABLE_CHAOS", "true")
    assert c.post("/admin/simulate-outage", params={"seconds": 5}).status_code == 200
    assert agent.in_outage() and c.get("/health").json()["status"] == "outage"


def test_worker_reports_task_errors_without_crashing():
    agent = WorkerAgent("W1", "http://x")
    body = asyncio.run(agent.run_one({"task_id": 1, "attempt": 1, "task_type": "bogus", "units": 5}))
    assert body["ok"] is False and "ValueError" in body["error"] and agent.state == "idle"
    body = asyncio.run(agent.run_one({"task_id": 2, "attempt": 1, "task_type": "prime_count", "units": 100}))
    assert body["ok"] and body["result"] == run_task("prime_count", 100) and body["exec_seconds"] > 0


def test_dashboard_client_against_coordinator(tmp_path):
    app = coordinator(algorithm="round_robin")
    tc = TestClient(app)
    register(tc)
    api = CoordinatorClient("http://testserver", client=tc)
    api.post("/tasks/submit", {"task_type": "sha256_chain", "units": 1000})
    snap = api.snapshot()
    assert snap["stats"]["run"]["submitted"] == 1 and len(snap["workers"]) == 3 and len(snap["tasks"]) == 1
    assert task_distribution(snap["workers"])[0] == {"worker_id": "W1", "assigned": 1, "completed": 0}
    assert len(api.metrics_history(["W1", "W2"])) == 2
    with pytest.raises(RuntimeError, match="409"):
        api.set_algorithm("least_loaded")
    with pytest.raises(RuntimeError, match="400"):
        api.post("/tasks/submit", {"task_type": "bad", "units": 1})
    (tmp_path / "live-x").mkdir()
    (tmp_path / "live-x" / "algorithm_summary.csv").write_text("algorithm\nround_robin\n")
    assert [p.parent.name for p in find_live_results(tmp_path)] == ["live-x"]
    assert find_live_results(tmp_path / "missing") == []


async def _e2e(algorithm, n_tasks, outage_worker=None, outage_seconds=0.0):
    app = coordinator(algorithm=algorithm, heartbeat_interval=0.1, unavailable_after=0.4, failed_after=0.8)
    cluster = app.state.cluster
    transport = httpx.ASGITransport(app=app)
    agents = []
    for wid, cap, w in WORKERS:
        client = httpx.AsyncClient(transport=transport, base_url="http://coord", timeout=10)
        agents.append(WorkerAgent(wid, "http://coord", cap, w, heartbeat_interval=0.1, poll_wait=0.5,
                                  client=client))
    loops = [asyncio.create_task(f()) for a in agents for f in (a.heartbeat_loop, a.work_loop)]

    async def monitor():
        while True:
            await asyncio.sleep(0.05)
            cluster.check_health()

    mon = asyncio.create_task(monitor())
    await asyncio.sleep(0.3)
    async with httpx.AsyncClient(transport=transport, base_url="http://coord") as c:
        specs = [{"task_type": t, "units": u} for t, u in
                 [("prime_count", 3000), ("data_aggregation", 4000), ("sha256_chain", 6000)] * (n_tasks // 3)]
        ids = (await c.post("/tasks/submit", json={"tasks": specs})).json()["task_ids"]
        if outage_worker:
            next(a for a in agents if a.worker_id == outage_worker).simulate_outage(outage_seconds)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            run = (await c.get("/scheduler/stats")).json()["run"]
            if run["completed"] + run["failed"] == len(ids):
                break
            await asyncio.sleep(0.05)
        if outage_worker:   # wait for the partitioned worker to come back
            while time.monotonic() < deadline and cluster.workers[outage_worker].status != "active":
                await asyncio.sleep(0.05)
        tasks = (await c.get("/tasks", params={"limit": 1000})).json()["tasks"]
    for a in agents:
        a.stop()
    for t in loops + [mon]:
        t.cancel()
    await asyncio.gather(*loops, mon, return_exceptions=True)
    return cluster, tasks, specs


@pytest.mark.parametrize("algorithm", ["round_robin", "weighted_round_robin", "least_loaded",
                                       "shortest_job_first", "fcfs_baseline"])
def test_end_to_end_real_execution(algorithm):
    cluster, tasks, specs = asyncio.run(_e2e(algorithm, 12))
    assert len(tasks) == 12 and all(t["status"] == "completed" for t in tasks)
    for t, s in zip(tasks, specs):
        assert t["result"] == run_task(s["task_type"], s["units"])   # real, verifiable result
        assert t["exec_seconds"] > 0 and t["network_overhead_seconds"] >= 0
    assert sum(w.mirror.tasks_completed for w in cluster.workers.values()) == 12


def test_end_to_end_worker_outage_recovers_all_tasks():
    cluster, tasks, _ = asyncio.run(_e2e("round_robin", 24, outage_worker="W2", outage_seconds=1.5))
    assert all(t["status"] == "completed" for t in tasks), [t["status"] for t in tasks]
    kinds = [e["type"] for e in cluster.events]
    assert "worker_failed" in kinds and "worker_recovered" in kinds
    assert cluster.workers["W2"].status == "active"


import json  # noqa: E402
from live.dashboard.api import (  # noqa: E402
    WebsiteClient, backend_rows, comparison_rows, parse_cpu_limits,
)


def _website_transport(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.host, request.url.path))
        p = request.url.path
        if p == "/gateway/stats":
            return httpx.Response(200, json={"algorithm": "least_loaded", "backends": []})
        if p in ("/gateway/reset", "/gateway/algorithm", "/gateway/backends/B2/outage", "/gateway/backends/B1/crash"):
            return httpx.Response(200, json={"ok": True})
        if p == "/loadgen/start":
            return httpx.Response(202, json={"run_id": 1, "echo": json.loads(request.content)})
        if p == "/loadgen/stop":
            return httpx.Response(409, json={"detail": "No website workload is running"})
        if p == "/api/v1/query":
            return httpx.Response(200, json={"data": {"result": [
                {"metric": {"replica": "B1"}, "value": [0, "0.3"]}]}})
        if p == "/api/v1/query_range":
            return httpx.Response(200, json={"data": {"result": [
                {"metric": {"replica": "B2"}, "values": [[1, "0.1"], [6, "0.2"]]}]}})
        return httpx.Response(404)
    return httpx.MockTransport(handler)


def test_website_client_start_resets_gateway_and_labels_run():
    calls = []
    c = WebsiteClient("http://gw", "http://lg", "http://prom", transport=_website_transport(calls))
    out = c.start(100, 20, "browse", 7, 32, fresh_run=True)
    assert out["echo"] == {"num_requests": 100, "rate": 20, "mix": "browse", "seed": 7, "max_concurrency": 32,
                           "label": "least_loaded | browse | seed 7"}
    assert ("POST", "gw", "/gateway/reset") in calls
    calls.clear()
    c.start(5, 1, "mixed", 1, 1, fresh_run=False)
    assert ("POST", "gw", "/gateway/reset") not in calls
    c.simulate_outage("B2", 10)
    c.crash_backend("B1", 15)
    assert ("POST", "gw", "/gateway/backends/B1/crash") in calls
    with pytest.raises(RuntimeError, match="409"):
        c.stop()
    assert c.prom_instant("x") == {"B1": 0.3}
    assert c.prom_range("x") == [{"time": 1.0, "replica": "B2", "value": 0.1},
                                 {"time": 6.0, "replica": "B2", "value": 0.2}]


def test_website_client_without_prometheus():
    c = WebsiteClient("http://gw", "http://lg", None, transport=_website_transport([]))
    assert c.prom_instant("x") == {} and c.prom_range("x") == []


def test_parse_cpu_limits():
    assert parse_cpu_limits("B1=0.75, B2=0.45,bad,B3=x,B4=0") == {"B1": 0.75, "B2": 0.45}


def test_backend_and_comparison_rows():
    backends = [
        {"backend_id": "B1", "healthy": True, "slots": 4, "inflight": 1, "assigned": 6, "completed": 6, "errors": 0,
         "avg_wait_ms": 1.0, "avg_service_ms": 10.0, "p95_service_ms": 20.0, "simulated_outage_remaining_s": 0},
        {"backend_id": "B2", "healthy": False, "slots": 2, "inflight": 0, "assigned": 2, "completed": 2, "errors": 1,
         "avg_wait_ms": None, "avg_service_ms": None, "p95_service_ms": None, "simulated_outage_remaining_s": 12.4},
    ]
    rows = backend_rows(backends, {"B1": 0.375}, {"B1": 50 * 2**20}, {"B1": 0.75, "B2": 0.45})
    assert rows[0]["CPU % of limit"] == 50.0 and rows[0]["memory MB"] == 50.0 and rows[0]["share %"] == 75.0
    assert rows[1]["status"] == "outage (12s left)" and rows[1]["CPU % of limit"] is None
    backends[1]["simulated_outage_remaining_s"] = 0
    assert backend_rows(backends, {}, {}, {})[1]["status"] == "DOWN (crashed)"
    run = {"run_id": 3, "algorithm": "round_robin", "mix": "mixed", "seed": 42, "state": "completed",
           "completed": 100, "target_rate_rps": 20, "achieved_rps": 19.5, "avg_ms": 30, "p50_ms": 25,
           "p95_ms": 60, "p99_ms": 90, "error_rate_pct": 0.0, "share_per_backend": {"B1": 40.0, "B2": 60.0}}
    out = comparison_rows([run])
    assert out[0]["algorithm"] == "round_robin" and out[0]["B1 %"] == 40.0 and out[0]["p95 ms"] == 60

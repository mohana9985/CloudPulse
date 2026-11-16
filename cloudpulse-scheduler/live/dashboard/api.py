from __future__ import annotations

import csv
from pathlib import Path

import httpx


class CoordinatorClient:
    def __init__(self, base_url: str, timeout: float = 5.0, client: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(base_url=self.base_url, timeout=timeout)

    def get(self, path: str, **params) -> dict:
        r = self.client.get(path, params=params or None)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, json: dict | None = None, **params) -> dict:
        r = self.client.post(path, json=json, params=params or None)
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except ValueError:
                detail = r.text
            raise RuntimeError(f"{r.status_code}: {detail}")
        return r.json() if r.content else {}

    def snapshot(self, task_limit: int = 300) -> dict:
        stats = self.get("/scheduler/stats")
        workers = self.get("/workers")["workers"]
        tasks = self.get("/tasks", limit=task_limit, offset=max(0, stats["run"]["submitted"] - task_limit))["tasks"]
        return {
            "stats": stats,
            "workers": workers,
            "tasks": tasks,
            "events": self.get("/events", limit=300)["events"],
            "runs": self.get("/scheduler/runs"),
            "algorithms": self.get("/scheduler/algorithms"),
        }

    def metrics_history(self, worker_ids: list[str], since: float = 0.0) -> list[dict]:
        rows = []
        for wid in worker_ids:
            for s in self.get(f"/workers/{wid}/metrics", since=since)["samples"]:
                rows.append({"worker_id": wid, **s})
        return rows

    def set_algorithm(self, name: str) -> dict:
        return self.post("/scheduler/algorithm", {"algorithm": name})

    def start_workload(self, num_tasks: int, seed: int, load: float, label: str = "") -> dict:
        return self.post("/workloads/start", {"num_tasks": num_tasks, "seed": seed, "load": load, "label": label})

    def reset(self, label: str = "") -> dict:
        return self.post("/scheduler/reset", {"label": label})

    def simulate_outage(self, worker_url: str, seconds: float) -> dict:
        r = httpx.post(f"{worker_url.rstrip('/')}/admin/simulate-outage", params={"seconds": seconds}, timeout=5)
        if r.status_code >= 400:
            raise RuntimeError(f"{r.status_code}: {r.text}")
        return r.json()


def task_distribution(workers: list[dict]) -> list[dict]:
    return [{"worker_id": w["worker_id"], "assigned": w["assigned_tasks"], "completed": w["completed_tasks"]}
            for w in workers]


def load_csv_rows(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def find_live_results(results_dir: Path) -> list[Path]:
    if not results_dir.is_dir():
        return []
    return sorted(results_dir.glob("live-*/algorithm_summary.csv"), key=lambda p: p.stat().st_mtime, reverse=True)


class WebsiteClient:

    def __init__(self, gateway_url: str, loadgen_url: str, prometheus_url: str | None = None,
                 timeout: float = 5.0, transport: httpx.BaseTransport | None = None) -> None:
        self.gateway = CoordinatorClient(gateway_url, client=httpx.Client(
            base_url=gateway_url.rstrip("/"), timeout=timeout, transport=transport))
        self.loadgen = CoordinatorClient(loadgen_url, client=httpx.Client(
            base_url=loadgen_url.rstrip("/"), timeout=timeout, transport=transport))
        self.prom = None if not prometheus_url else httpx.Client(
            base_url=prometheus_url.rstrip("/"), timeout=timeout, transport=transport)

    def snapshot(self) -> dict:
        return {
            "gateway": self.gateway.get("/gateway/stats"),
            "events": self.gateway.get("/gateway/events", limit=100)["events"],
            "gateway_runs": self.gateway.get("/gateway/runs")["runs"],
            "loadgen": self.loadgen.get("/loadgen/status"),
            "recent": self.loadgen.get("/loadgen/recent", limit=150)["items"],
            "loadgen_runs": self.loadgen.get("/loadgen/runs")["runs"],
        }

    def mixes(self) -> dict:
        return self.loadgen.get("/loadgen/config")["mixes"]

    def set_algorithm(self, name: str) -> dict:
        return self.gateway.post("/gateway/algorithm", {"algorithm": name})

    def start(self, num_requests: int, rate: float, mix: str, seed: int, max_concurrency: int,
              fresh_run: bool = True) -> dict:
        algo = self.gateway.get("/gateway/stats")["algorithm"]
        label = f"{algo} | {mix} | seed {seed}"
        if fresh_run:
            self.gateway.post("/gateway/reset", {"label": ""})
        return self.loadgen.post("/loadgen/start", {"num_requests": num_requests, "rate": rate, "mix": mix,
                                                    "seed": seed, "max_concurrency": max_concurrency,
                                                    "label": label})

    def stop(self) -> dict:
        return self.loadgen.post("/loadgen/stop")

    def simulate_outage(self, backend_id: str, seconds: float) -> dict:
        return self.gateway.post(f"/gateway/backends/{backend_id}/outage", {"seconds": seconds})

    def crash_backend(self, backend_id: str, down_seconds: float) -> dict:
        return self.gateway.post(f"/gateway/backends/{backend_id}/crash", {"down_seconds": down_seconds})

    def prom_instant(self, expr: str) -> dict[str, float]:
        if self.prom is None:
            return {}
        try:
            r = self.prom.get("/api/v1/query", params={"query": expr})
            r.raise_for_status()
            return {s["metric"].get("replica", "?"): float(s["value"][1]) for s in r.json()["data"]["result"]}
        except (httpx.HTTPError, KeyError, ValueError):
            return {}

    def prom_range(self, expr: str, minutes: float = 10, step: int = 5) -> list[dict]:
        if self.prom is None:
            return []
        import time as _time
        end = _time.time()
        try:
            r = self.prom.get("/api/v1/query_range",
                              params={"query": expr, "start": end - minutes * 60, "end": end, "step": step})
            r.raise_for_status()
            rows = []
            for s in r.json()["data"]["result"]:
                rep = s["metric"].get("replica", "?")
                rows += [{"time": float(t), "replica": rep, "value": float(v)} for t, v in s["values"]]
            return rows
        except (httpx.HTTPError, KeyError, ValueError):
            return []


BACKEND_CPU_QUERY = 'rate(process_cpu_seconds_total{job="cloudpulse-store-backend"}[1m])'
BACKEND_MEM_QUERY = 'process_resident_memory_bytes{job="cloudpulse-store-backend"}'


def parse_cpu_limits(text: str) -> dict[str, float]:
    out = {}
    for part in (text or "").split(","):
        k, _, v = part.partition("=")
        try:
            out[k.strip()] = float(v)
        except ValueError:
            continue
    return {k: v for k, v in out.items() if k and v > 0}


def backend_rows(backends: list[dict], cpu_cores: dict[str, float], mem_bytes: dict[str, float],
                 cpu_limits: dict[str, float]) -> list[dict]:
    total = sum(b["completed"] for b in backends) or 1
    rows = []
    for b in backends:
        bid = b["backend_id"]
        cores, limit = cpu_cores.get(bid), cpu_limits.get(bid)
        outage = b.get("simulated_outage_remaining_s") or 0
        rows.append({
            "backend": bid,
            "status": "healthy" if b["healthy"] else (f"outage ({outage:.0f}s left)" if outage else "DOWN (crashed)"),
            "CPU limit (cores)": limit,
            "CPU % of limit": None if cores is None or not limit else round(100 * cores / limit, 1),
            "memory MB": None if bid not in mem_bytes else round(mem_bytes[bid] / 2**20, 1),
            "slots": b["slots"],
            "in flight": b["inflight"],
            "assigned": b["assigned"],
            "completed": b["completed"],
            "share %": round(100 * b["completed"] / total, 1),
            "errors": b["errors"],
            "avg wait ms": b["avg_wait_ms"],
            "avg service ms": b["avg_service_ms"],
            "p95 service ms": b["p95_service_ms"],
        })
    return rows


def comparison_rows(runs: list[dict]) -> list[dict]:
    rows = []
    for r in runs:
        row = {"run": r["run_id"], "algorithm": r.get("algorithm") or "?", "mix": r["mix"], "seed": r["seed"],
               "state": r["state"], "requests": r["completed"], "target req/s": r["target_rate_rps"],
               "achieved req/s": r["achieved_rps"], "avg ms": r["avg_ms"], "p50 ms": r["p50_ms"],
               "p95 ms": r["p95_ms"], "p99 ms": r["p99_ms"], "error %": r["error_rate_pct"]}
        for k, v in (r.get("share_per_backend") or {}).items():
            row[f"{k} %"] = v
        rows.append(row)
    return rows

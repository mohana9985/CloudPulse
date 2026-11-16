# Every (size, seed) workload is generated once by the coordinator from the same seed, so all
# algorithms receive the identical task list (checked by SHA-256 fingerprint).
from __future__ import annotations

import argparse
import csv
import json
import platform
import statistics
import subprocess
import time
from datetime import datetime
from pathlib import Path

import httpx

from src.schedulers import ALL_CONFIGURATIONS

ROOT = Path(__file__).resolve().parents[2]
ALGOS = list(ALL_CONFIGURATIONS)
WORKER_SERVICES = {"W1": "worker-1", "W2": "worker-2", "W3": "worker-3"}


class Runner:
    def __init__(self, url: str, out: Path, setup: str, compose_dir: Path, expect: list[str]) -> None:
        self.c = httpx.Client(base_url=url.rstrip("/"), timeout=30)
        self.out = out
        self.setup = setup
        self.compose_dir = compose_dir
        self.expect = expect
        out.mkdir(parents=True, exist_ok=True)
        self.files: dict[str, tuple[Path, list[str] | None]] = {}

    def get(self, path, **params):
        r = self.c.get(path, params=params or None)
        r.raise_for_status()
        return r.json()

    def post(self, path, body=None):
        r = self.c.post(path, json=body or {})
        if r.status_code >= 400:
            raise RuntimeError(f"{path}: {r.status_code} {r.text}")
        return r.json()

    def docker(self, *args: str) -> None:
        subprocess.run(["docker", "compose", *args], cwd=self.compose_dir, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def wait_workers(self, ids: list[str], timeout: float = 90) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            ws = {w["worker_id"]: w for w in self.get("/workers")["workers"]}
            if all(ws.get(i, {}).get("status") == "active" for i in ids):
                return
            time.sleep(0.5)
        raise RuntimeError(f"workers {ids} not active after {timeout}s")

    def wait_idle(self, timeout: float = 600) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            s = self.get("/scheduler/stats")
            busy = s["tasks_by_status"]
            wl = s.get("workload") or {}
            if busy["pending"] + busy["queued"] + busy["running"] == 0 and wl.get("submitted", 0) >= wl.get(
                    "num_tasks", 0):
                return
            time.sleep(0.5)
        raise RuntimeError("run did not finish in time")

    def append(self, name: str, rows: list[dict]) -> None:
        if not rows:
            return
        path = self.out / name
        new = not path.exists()
        with path.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            if new:
                w.writeheader()
            w.writerows(rows)

    def run(self, scenario: str, algorithm: str, size: int, seed: int, load: float,
            total_capacity: float | None = None, fail: dict | None = None, workers: list[str] | None = None) -> dict:
        workers = workers or self.expect
        self.wait_workers(workers)
        self.wait_idle()
        self.post("/scheduler/reset", {"label": scenario})
        self.post("/scheduler/algorithm", {"algorithm": algorithm})
        t_start = self.get("/scheduler/stats")["uptime_seconds"]
        body = {"num_tasks": size, "seed": seed, "load": load, "label": scenario}
        if total_capacity:
            body["total_capacity"] = total_capacity
        info = self.post("/workloads/start", body)
        injected = None
        if fail:
            time.sleep(fail["at"])
            injected = self.get("/health")["server_time"]
            self.docker("kill", WORKER_SERVICES[fail["worker"]])        # hard crash (SIGKILL)
            time.sleep(fail["down"])
            self.docker("start", WORKER_SERVICES[fail["worker"]])
        self.wait_idle()
        t_end = self.get("/scheduler/stats")["uptime_seconds"]
        stats = self.get("/scheduler/stats")
        tasks = self.get("/tasks", limit=5000)["tasks"]
        events = [e for e in self.get("/events", since=t_start, limit=5000)["events"]]
        wview = {w["worker_id"]: w for w in self.get("/workers")["workers"]}
        samples = {wid: [s for s in self.get(f"/workers/{wid}/metrics", since=t_start)["samples"] if s["t"] <= t_end]
                   for wid in wview}
        run = stats["run"]
        key = {"setup": self.setup, "scenario": scenario, "algorithm": algorithm, "size": size, "seed": seed,
               "load": load, "workers": "+".join(workers), "workload_fingerprint": info["fingerprint"][:16]}

        done = [t for t in tasks if t["status"] == "completed"]
        waits = sorted(t["waiting_seconds"] for t in done)
        row = {
            **key,
            "submitted": run["submitted"], "completed": run["completed"], "failed": run["failed"],
            "lost": run["submitted"] - run["completed"] - run["failed"],
            "retries": run["retries"],
            "makespan_s": run["makespan_seconds"],
            "throughput_tps": run["throughput_tasks_per_second"],
            "avg_exec_s": run["avg_exec_seconds"],
            "avg_wait_s": run["avg_waiting_seconds"],
            "p95_wait_s": waits[int(0.95 * (len(waits) - 1))] if waits else None,
            "max_wait_s": waits[-1] if waits else None,
            "avg_turnaround_s": run["avg_turnaround_seconds"],
            "avg_net_overhead_ms": None if run["avg_network_overhead_seconds"] is None
            else round(run["avg_network_overhead_seconds"] * 1000, 3),
        }
        if fail:
            failed_ev = next((e for e in events if e["type"] == "worker_failed" and e["worker_id"] == fail["worker"]),
                             None)
            unav_ev = next((e for e in events if e["type"] == "worker_unavailable" and e["worker_id"] == fail["worker"]),
                           None)
            rec_ev = next((e for e in events if e["type"] == "worker_recovered" and e["worker_id"] == fail["worker"]),
                          None)
            affected = (failed_ev or {}).get("interrupted_tasks", []) + (failed_ev or {}).get("queued_tasks", [])
            by_id = {t["task_id"]: t for t in tasks}
            aff_done = [by_id[i]["completed_at"] for i in affected if by_id.get(i, {}).get("completed_at")]
            row.update({
                "failed_worker": fail["worker"],
                "kill_at_s": fail["at"], "down_for_s": fail["down"],
                "unavailable_after_kill_s": None if not unav_ev else round(unav_ev["unix"] - injected, 3),
                "detected_failed_after_kill_s": None if not failed_ev else round(failed_ev["unix"] - injected, 3),
                "interrupted_tasks": len((failed_ev or {}).get("interrupted_tasks", [])),
                "reassigned_queued_tasks": len((failed_ev or {}).get("queued_tasks", [])),
                "affected_recovered_s": None if not (failed_ev and aff_done)
                else round(max(aff_done) - failed_ev["t"], 3),
                "worker_rejoined_after_kill_s": None if not rec_ev else round(rec_ev["unix"] - injected, 3),
            })
        self.append(f"runs_{scenario}.csv", [row])

        per_worker = []
        for wid, w in sorted(wview.items()):
            mine = [t for t in done if t["worker_id"] == wid]
            ss = samples.get(wid, [])
            cpu = [s["cpu_percent_of_limit"] for s in ss if s.get("cpu_percent_of_limit") is not None]
            mem = [s.get("container_memory_mb") or s.get("process_rss_mb") for s in ss]
            mem = [m for m in mem if m is not None]
            per_worker.append({
                **key, "worker_id": wid, "host": w["host"], "capacity": w["capacity"],
                "cpu_limit_cores": (w.get("metrics") or {}).get("cpu_limit_cores"),
                "completed": len(mine), "share_pct": round(100 * len(mine) / len(done), 2) if done else 0,
                "busy_exec_s": round(sum(t["exec_seconds"] for t in mine), 4),
                "utilisation_pct": round(100 * sum(t["exec_seconds"] for t in mine) / run["makespan_seconds"], 2)
                if run["makespan_seconds"] else None,
                "mean_cpu_pct_of_limit": round(statistics.fmean(cpu), 2) if cpu else None,
                "max_cpu_pct_of_limit": round(max(cpu), 2) if cpu else None,
                "mean_memory_mb": round(statistics.fmean(mem), 2) if mem else None,
                "max_memory_mb": round(max(mem), 2) if mem else None,
                "samples": len(ss),
            })
        self.append(f"per_worker_{scenario}.csv", per_worker)
        self.append(f"tasks_{scenario}.csv", [
            {**key, **{k: t[k] for k in ("task_id", "task_type", "size_class", "units", "estimated_seconds",
                                         "status", "worker_id", "attempts", "exec_seconds", "cpu_seconds",
                                         "waiting_seconds", "turnaround_seconds", "network_overhead_seconds")}}
            for t in tasks])
        with (self.out / f"events_{scenario}.jsonl").open("a") as f:
            for e in events:
                f.write(json.dumps({**key, **e}) + "\n")
        print(f"  {scenario:8s} {algorithm:22s} n={size:<4d} seed={seed} done={row['completed']}/{row['submitted']} "
              f"lost={row['lost']} makespan={row['makespan_s']:.1f}s avg_turn={row['avg_turnaround_s'] or 0:.2f}s "
              f"thr={row['throughput_tps'] or 0:.2f}/s", flush=True)
        return row

    def metadata(self, argv: dict) -> None:
        ws = self.get("/workers")["workers"]
        git = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True)
        meta = {
            "measurement_type": "REAL execution on live workers (not simulated)",
            "setup": self.setup, "created": datetime.now().isoformat(timespec="seconds"),
            "git_commit": git.stdout.strip() or None, "runner_host": platform.platform(),
            "workers": [{k: w[k] for k in ("worker_id", "host", "capacity", "weight")} |
                        {"cpu_limit_cores": (w.get("metrics") or {}).get("cpu_limit_cores")} for w in ws],
            "args": argv,
        }
        (self.out / f"metadata_{argv['scenario']}.json").write_text(json.dumps(meta, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("scenario", choices=["grid", "failure", "scaling"])
    p.add_argument("--coordinator", default="http://localhost:8100")
    p.add_argument("--experiment-id", default=None)
    p.add_argument("--setup", default="single-host-docker",
                   help="label recorded with every row, e.g. single-host-docker, ec2-single-host, multi-host")
    p.add_argument("--sizes", type=int, nargs="+", default=[30, 60, 120])
    p.add_argument("--size", type=int, default=60)
    p.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    p.add_argument("--load", type=float, default=0.85)
    p.add_argument("--algorithms", nargs="+", default=ALGOS)
    p.add_argument("--workers", nargs="+", default=["W1", "W2", "W3"])
    p.add_argument("--fail-worker", default="W2")
    p.add_argument("--fail-at", type=float, default=5.0)
    p.add_argument("--down-for", type=float, default=15.0)
    p.add_argument("--compose-dir", default=str(ROOT))
    a = p.parse_args()

    exp = a.experiment_id or f"live-{datetime.now():%Y%m%d-%H%M}"
    r = Runner(a.coordinator, ROOT / "results" / exp, a.setup, Path(a.compose_dir), a.workers)
    r.metadata(vars(a))
    print(f"Writing to results/{exp}/  (REAL execution, setup={a.setup})")
    if a.scenario == "grid":
        for size in a.sizes:
            for seed in a.seeds:
                for alg in a.algorithms:
                    r.run("grid", alg, size, seed, a.load)
    elif a.scenario == "failure":
        for seed in a.seeds:
            for alg in a.algorithms:
                r.run("normal", alg, a.size, seed, a.load)
                r.run("failure", alg, a.size, seed, a.load,
                      fail={"worker": a.fail_worker, "at": a.fail_at, "down": a.down_for})
    else:  # scaling: same workload (rate fixed for total capacity 2.0) on 1, 2 and 3 workers
        sets = [a.workers[:k] for k in range(1, len(a.workers) + 1)]
        for seed in a.seeds:
            for subset in sets:
                off = [w for w in a.workers if w not in subset]
                for w in off:
                    r.docker("stop", WORKER_SERVICES[w])
                for w in subset:
                    r.docker("start", WORKER_SERVICES[w])
                r.wait_workers(subset)
                time.sleep(12 if off else 0)          # let stopped workers be marked failed first
                for alg in a.algorithms:
                    r.run("scaling", alg, a.size, seed, a.load, total_capacity=2.0, workers=subset)
        for w in a.workers:
            r.docker("start", WORKER_SERVICES[w])
    print("done")


if __name__ == "__main__":
    main()

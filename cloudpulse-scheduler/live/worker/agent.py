# Workers only need OUTBOUND access to the coordinator, so a worker on another machine
# joins by setting COORDINATOR_URL.
from __future__ import annotations

import asyncio
import logging
import os
import socket
import time
import uuid

import httpx

from ..tasks import run_task
from .metrics import MetricsSampler

log = logging.getLogger("cloudpulse.worker")


class WorkerAgent:
    def __init__(
        self,
        worker_id: str,
        coordinator_url: str,
        capacity: float = 1.0,
        weight: int = 1,
        heartbeat_interval: float = 2.0,
        poll_wait: float = 20.0,
        client: httpx.AsyncClient | None = None,
        sampler: MetricsSampler | None = None,
        url: str | None = None,
    ) -> None:
        self.url = url
        self.worker_id = worker_id
        self.coordinator_url = coordinator_url.rstrip("/")
        self.capacity = capacity
        self.weight = weight
        self.heartbeat_interval = heartbeat_interval
        self.poll_wait = poll_wait
        self.boot_id = uuid.uuid4().hex
        self.host = socket.gethostname()
        self.sampler = sampler or MetricsSampler()
        # client timeout > server long-poll wait so the server never "delivers" to a gone client
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(poll_wait + 15.0, connect=5.0))
        self.state = "idle"
        self.current_task: dict | None = None
        self.completed = 0
        self.errors = 0
        self.last_heartbeat_ok: float | None = None
        self.outage_until = 0.0   # simulated outage (network partition) end time, monotonic
        self._stop = asyncio.Event()

    def in_outage(self) -> bool:
        return time.monotonic() < self.outage_until

    def simulate_outage(self, seconds: float) -> None:
        self.outage_until = time.monotonic() + seconds

    def heartbeat_payload(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "boot_id": self.boot_id,
            "capacity": self.capacity,
            "weight": self.weight,
            "host": self.host,
            "pid": os.getpid(),
            "cpu_limit_cores": self.sampler.cpu_limit_cores,
            "url": self.url,
            "state": self.state,
            "metrics": self.sampler.sample(),
        }

    async def send_heartbeat(self) -> bool:
        if self.in_outage():
            return False
        try:
            r = await self.client.post(f"{self.coordinator_url}/workers/heartbeat", json=self.heartbeat_payload())
            r.raise_for_status()
            self.last_heartbeat_ok = time.time()
            return True
        except httpx.HTTPError as e:
            log.warning("heartbeat failed: %s", e)
            return False

    async def heartbeat_loop(self) -> None:
        while not self._stop.is_set():
            await self.send_heartbeat()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.heartbeat_interval)
            except asyncio.TimeoutError:
                pass

    @staticmethod
    def _execute(task_type: str, units: int) -> tuple[dict, float, float]:
        wall0, cpu0 = time.perf_counter(), time.thread_time()
        result = run_task(task_type, units)
        return result, time.perf_counter() - wall0, time.thread_time() - cpu0

    async def run_one(self, assignment: dict) -> dict:
        self.state, self.current_task = "busy", assignment
        try:
            result, wall, cpu = await asyncio.to_thread(self._execute, assignment["task_type"], assignment["units"])
            body = {"worker_id": self.worker_id, "attempt": assignment["attempt"], "ok": True,
                    "exec_seconds": round(wall, 6), "cpu_seconds": round(cpu, 6), "result": result}
            self.completed += 1
        except Exception as e:  # task code failed: report it, do not crash the worker
            self.errors += 1
            body = {"worker_id": self.worker_id, "attempt": assignment["attempt"], "ok": False,
                    "exec_seconds": 0.0, "error": f"{type(e).__name__}: {e}"}
        finally:
            self.state, self.current_task = "idle", None
        return body

    async def report(self, task_id: int, body: dict) -> None:
        for attempt in range(5):
            if self.in_outage():
                return  # partitioned: the result never reaches the coordinator
            try:
                r = await self.client.post(f"{self.coordinator_url}/tasks/{task_id}/result", json=body)
                r.raise_for_status()
                return
            except httpx.HTTPError as e:
                log.warning("result report failed (%s), retrying", e)
                await asyncio.sleep(0.5 * (attempt + 1))

    async def work_loop(self) -> None:
        while not self._stop.is_set():
            if self.in_outage():
                await asyncio.sleep(0.5)
                continue
            try:
                r = await self.client.post(f"{self.coordinator_url}/workers/{self.worker_id}/poll",
                                           params={"wait": self.poll_wait})
                if r.status_code == 204:
                    continue
                if r.status_code == 404:
                    await self.send_heartbeat()
                    await asyncio.sleep(0.5)
                    continue
                r.raise_for_status()
                assignment = r.json()
            except httpx.HTTPError as e:
                log.warning("poll failed: %s", e)
                await asyncio.sleep(1.0)
                continue
            body = await self.run_one(assignment)
            await self.report(assignment["task_id"], body)

    def stop(self) -> None:
        self._stop.set()

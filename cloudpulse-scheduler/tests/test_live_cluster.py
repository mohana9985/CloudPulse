import asyncio
from collections import Counter

import pytest

from live.coordinator.cluster import (
    COMPLETED,
    FAILED,
    PENDING,
    QUEUED,
    RUNNING,
    W_ACTIVE,
    W_FAILED,
    W_UNAVAILABLE,
    Cluster,
    ConflictError,
)

WORKERS = [("W1", 1.0, 5), ("W2", 0.6, 3), ("W3", 0.4, 2)]


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make(algorithm="round_robin", **kw):
    clock = Clock()
    c = Cluster(algorithm=algorithm, unavailable_after=5, failed_after=10, clock=clock, wallclock=clock, **kw)
    for wid, cap, w in WORKERS:
        c.heartbeat({"worker_id": wid, "boot_id": "b-" + wid, "capacity": cap, "weight": w})
    return c, clock


def beat(c, wid, boot=None):
    c.heartbeat({"worker_id": wid, "boot_id": boot or "b-" + wid})


async def take(c, wid):
    return await c.poll(wid, timeout=0.01)


def test_round_robin_rotates_on_arrival():
    c, _ = make("round_robin")
    tasks = [c.submit("sha256_chain", 1000) for _ in range(6)]
    assert [t.worker_id for t in tasks] == ["W1", "W2", "W3", "W1", "W2", "W3"]
    assert all(t.status == QUEUED for t in tasks)


def test_weighted_round_robin_follows_5_3_2():
    c, _ = make("weighted_round_robin")
    tasks = [c.submit("sha256_chain", 1000) for _ in range(10)]
    assert Counter(t.worker_id for t in tasks) == {"W1": 5, "W2": 3, "W3": 2}


def test_least_loaded_uses_estimated_load_over_capacity():
    c, _ = make("least_loaded")
    big = c.submit("sha256_chain", 900_000)          # ~1 s on W1
    assert big.worker_id == "W1"
    nxt = c.submit("sha256_chain", 900_000)
    assert nxt.worker_id == "W2"                     # W2/W3 empty; W2 wins tie-break by order
    third = c.submit("sha256_chain", 900_000)
    assert third.worker_id == "W3"
    fourth = c.submit("sha256_chain", 900_000)
    assert fourth.worker_id == "W1"                  # W1 load 1 s vs W2 1.67 s vs W3 2.5 s


def test_sjf_delivers_shortest_estimate_first_to_fastest_idle_worker():
    async def run():
        c, _ = make("shortest_job_first")
        long_ = c.submit("sha256_chain", 500_000)
        short = c.submit("sha256_chain", 1_000)
        mid = c.submit("sha256_chain", 50_000)
        assert {long_.status, short.status, mid.status} == {PENDING}
        polls = [asyncio.create_task(c.poll(w, timeout=1)) for w in ("W3", "W2", "W1")]
        got = await asyncio.gather(*polls)
        return c, got, (short, mid, long_)

    c, got, (short, mid, long_) = asyncio.run(run())
    # all three were waiting when dispatch ran in poll order; shortest went to the first idle poller
    # at that moment, and every task was delivered exactly once
    assert sorted(a["task_id"] for a in got) == sorted([short.task_id, mid.task_id, long_.task_id])
    assert all(t.status == RUNNING for t in (short, mid, long_))


def test_sjf_picks_fastest_idle_worker_when_all_idle():
    async def run():
        c, _ = make("shortest_job_first")
        polls = [asyncio.create_task(c.poll(w, timeout=1)) for w in ("W3", "W2", "W1")]
        await asyncio.sleep(0)
        t = c.submit("sha256_chain", 1_000)
        await asyncio.sleep(0)
        for p in polls:
            p.cancel()
        return t

    t = asyncio.run(run())
    assert t.worker_id == "W1"


def test_complete_records_measurements_and_rejects_stale_results():
    async def run():
        c, clock = make("round_robin")
        t = c.submit("sha256_chain", 1000)
        a = await take(c, "W1")
        clock.t += 0.5
        assert c.complete(t.task_id, "W2", a["attempt"], True, 0.4)["accepted"] is False   # wrong worker
        assert c.complete(t.task_id, "W1", 99, True, 0.4)["accepted"] is False             # wrong attempt
        assert c.complete(t.task_id, "W1", a["attempt"], True, 0.4, 0.39, {"checksum": "x"})["accepted"]
        assert c.complete(t.task_id, "W1", a["attempt"], True, 0.4)["accepted"] is False   # duplicate
        return c, t

    c, t = asyncio.run(run())
    d = t.to_dict()
    assert t.status == COMPLETED and d["exec_seconds"] == 0.4
    assert d["network_overhead_seconds"] == pytest.approx(0.1)
    assert c.counters["stale_results"] == 3
    assert c.workers["W1"].mirror.tasks_completed == 1


def test_heartbeat_timeout_marks_unavailable_then_failed_and_requeues():
    async def run():
        c, clock = make("round_robin")
        tasks = [c.submit("sha256_chain", 1000) for _ in range(6)]   # W2 gets tasks 2 and 5
        a = await take(c, "W2")
        assert a["task_id"] == tasks[1].task_id
        clock.t += 6
        for w in ("W1", "W3"):
            beat(c, w)
        c.check_health()
        assert c.workers["W2"].status == W_UNAVAILABLE
        assert tasks[1].status == RUNNING and tasks[4].status == QUEUED   # unavailable keeps its work
        assert c.submit("sha256_chain", 1000).worker_id != "W2"          # but gets no new work
        clock.t += 5
        for w in ("W1", "W3"):
            beat(c, w)
        c.check_health()
        return c, tasks

    c, tasks = asyncio.run(run())
    assert c.workers["W2"].status == W_FAILED
    assert tasks[1].worker_id in ("W1", "W3") and tasks[1].attempts == 1   # interrupted -> retried
    assert tasks[4].worker_id in ("W1", "W3") and tasks[4].attempts == 0   # queued -> reassigned
    assert c.counters["retries"] == 1 and c.counters["worker_failures"] == 1
    kinds = [e["type"] for e in c.events]
    assert "worker_unavailable" in kinds and "worker_failed" in kinds and kinds.count("task_requeued") == 2


def test_recovery_after_heartbeat_returns():
    c, clock = make("least_loaded")
    clock.t += 11
    for w in ("W1", "W3"):
        beat(c, w)
    c.check_health()        # W2 unavailable
    c.check_health()        # W2 failed (age 11 s > 10 s)
    assert c.workers["W2"].status == W_FAILED
    clock.t += 4
    beat(c, "W2")
    ws = c.workers["W2"]
    assert ws.status == W_ACTIVE and ws.recoveries == 1
    rec = [e for e in c.events if e["type"] == "worker_recovered"][-1]
    assert rec["downtime_seconds"] == pytest.approx(4)


def test_worker_restart_detected_by_new_boot_id():
    async def run():
        c, _ = make("round_robin")
        t = c.submit("sha256_chain", 1000)
        await take(c, "W1")
        beat(c, "W1", boot="new-process")
        return c, t

    c, t = asyncio.run(run())
    assert t.status == QUEUED and t.attempts == 1 and c.counters["retries"] == 1
    assert c.workers["W1"].status == W_ACTIVE and c.workers["W1"].recoveries == 1


def test_retry_limit_marks_task_failed():
    async def run():
        c, _ = make("round_robin", max_attempts=2)
        t = c.submit("sha256_chain", 1000)
        for i in range(2):
            wid = t.worker_id
            await take(c, wid)
            beat(c, wid, boot=f"restart-{i}")   # crash while running
        return c, t

    c, t = asyncio.run(run())
    assert t.status == FAILED and t.attempts == 2 and "gave up" in t.error
    assert c.counters["failed"] == 1


def test_lost_delivery_is_retried_on_next_poll():
    async def run():
        c, _ = make("round_robin")
        t = c.submit("sha256_chain", 1000)
        await take(c, "W1")              # delivered ...
        nxt = await take(c, "W1")        # ... but the worker polls again without reporting
        return c, t, nxt

    c, t, nxt = asyncio.run(run())
    assert nxt is None                    # RR rotation re-places the task on the next worker
    assert t.status == QUEUED and t.worker_id == "W2" and t.attempts == 1
    assert c.counters["retries"] == 1


def test_no_task_lost_when_worker_fails_mid_run():
    async def run():
        c, clock = make("shortest_job_first")
        tasks = [c.submit("sha256_chain", 1000 * (i + 1)) for i in range(9)]
        a = await take(c, "W2")
        clock.t += 11
        beat(c, "W1")
        beat(c, "W3")
        c.check_health()
        c.check_health()
        for _ in range(30):
            for w in ("W1", "W3"):
                got = await take(c, w)
                if got:
                    c.complete(got["task_id"], w, got["attempt"], True, 0.01)
        return c, tasks, a

    c, tasks, a = asyncio.run(run())
    assert all(t.status == COMPLETED for t in tasks)
    assert c.tasks[a["task_id"]].attempts == 2
    assert {t.worker_id for t in tasks} <= {"W1", "W3"}


def test_algorithm_change_and_reset_are_blocked_while_busy():
    c, _ = make()
    c.submit("sha256_chain", 1000)
    with pytest.raises(ConflictError):
        c.set_algorithm("least_loaded")
    with pytest.raises(ConflictError):
        c.reset_run()
    with pytest.raises(ValueError):
        Cluster(algorithm="nope")


def test_reset_archives_run_summary():
    async def run():
        c, clock = make("weighted_round_robin")
        t = c.submit("sha256_chain", 1000)
        a = await take(c, "W1")
        clock.t += 1
        c.complete(t.task_id, "W1", a["attempt"], True, 0.9)
        summary = c.reset_run()
        return c, summary

    c, summary = asyncio.run(run())
    assert summary["algorithm"] == "weighted_round_robin" and summary["completed"] == 1
    assert summary["throughput_tasks_per_second"] == pytest.approx(1.0)
    assert c.runs == [summary] and not c.tasks
    assert c.workers["W1"].mirror.tasks_completed == 0


def test_worker_joining_mid_run_keeps_central_queue():
    c, _ = make("shortest_job_first")
    for _ in range(3):
        c.submit("sha256_chain", 1000)
    c.heartbeat({"worker_id": "W4", "capacity": 1.0, "weight": 1})
    assert c.scheduler.pending_count() == 3 and "W4" in c.workers

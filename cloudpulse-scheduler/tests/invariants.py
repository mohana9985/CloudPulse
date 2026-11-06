# Independent checker: re-derives everything from raw records instead of reusing
# engine or metrics code, so a bug there cannot hide itself.
from __future__ import annotations

from collections import Counter, defaultdict

EPS = 1e-9


def check_schedule(result, tasks, specs) -> list[str]:
    problems: list[str] = []
    by_id = {t.task_id: t for t in tasks}
    spec = {s.worker_id: s for s in specs}
    ids = [r.task_id for r in result.records]

    dupes = [i for i, c in Counter(ids).items() if c > 1]
    if dupes:
        problems.append(f"duplicate completions: {dupes[:5]}")
    missing = set(by_id) - set(ids)
    if missing:
        problems.append(f"missing tasks: {sorted(missing)[:5]}")
    extra = set(ids) - set(by_id)
    if extra:
        problems.append(f"unknown tasks: {sorted(extra)[:5]}")

    spans = defaultdict(list)
    for r in result.records:
        t = by_id.get(r.task_id)
        if t is None:
            continue
        s = spec[r.worker_id]
        if not s.available:
            problems.append(f"task {r.task_id} ran on unavailable worker {r.worker_id}")
        if r.arrival_time != t.arrival_time or r.actual_duration != t.actual_duration or r.estimated_duration != t.estimated_duration:
            problems.append(f"task {r.task_id} record does not match input")
        if r.start_time < t.arrival_time - EPS:
            problems.append(f"task {r.task_id} started before arrival")
        expected_exec = t.actual_duration / s.capacity
        if abs((r.completion_time - r.start_time) - expected_exec) > 1e-6:
            problems.append(f"task {r.task_id} wrong execution time")
        spans[r.worker_id].append((r.start_time, r.completion_time, r.task_id))

    for wid, intervals in spans.items():
        intervals.sort()
        for (s1, e1, a), (s2, e2, b) in zip(intervals, intervals[1:]):
            if s2 < e1 - EPS:
                problems.append(f"worker {wid} overlap: task {a} [{s1},{e1}) and task {b} [{s2},{e2})")
    return problems


def reference_metrics(result, specs) -> dict:
    recs = result.records
    n = len(recs)
    makespan = max((r.completion_time for r in recs), default=0.0)
    busy = defaultdict(float)
    for r in recs:
        busy[r.worker_id] += r.completion_time - r.start_time
    avail = [s.worker_id for s in specs if s.available]
    utils = [busy[w] / makespan * 100 if makespan else 0.0 for w in avail]
    waits = [r.start_time - r.arrival_time for r in recs]
    return {
        "tasks_completed": n,
        "avg_waiting_time": sum(waits) / n if n else 0.0,
        "max_waiting_time": max(waits, default=0.0),
        "avg_turnaround_time": sum(r.completion_time - r.arrival_time for r in recs) / n if n else 0.0,
        "makespan": makespan,
        "throughput": n / makespan if makespan else 0.0,
        "avg_worker_utilisation_pct": sum(utils) / len(utils) if utils else 0.0,
    }

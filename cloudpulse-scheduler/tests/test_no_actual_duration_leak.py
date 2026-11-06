import dataclasses
import re
from pathlib import Path

import pytest

import src.simulation_engine as engine_mod
from src.schedulers import ALL_CONFIGURATIONS, create_scheduler
from src.simulation_engine import run_simulation
from src.worker import Worker
from src.workload_generator import Task, WorkloadConfig, generate_workload

ALL = sorted(ALL_CONFIGURATIONS)
SCHEDULER_DIR = Path(__file__).resolve().parent.parent / "src" / "schedulers"
DECISION_METHODS = ("select_worker", "add_task", "pop_next_task", "select_idle_worker")

_state = {"in_decision": False, "violations": []}


class SpyTask(Task):
    def __getattribute__(self, name):
        if name == "actual_duration" and _state["in_decision"]:
            _state["violations"].append(f"Task.actual_duration read (task {object.__getattribute__(self, 'task_id')})")
        return object.__getattribute__(self, name)


class SpyWorker(Worker):
    def __getattribute__(self, name):
        if name in ("current_end", "execution_time") and _state["in_decision"]:
            _state["violations"].append(f"Worker.{name} read")
        return object.__getattribute__(self, name)


def _wrap_decisions(scheduler):
    for name in DECISION_METHODS:
        method = getattr(scheduler, name, None)
        if method is None:
            continue

        def wrapped(*args, _m=method, **kwargs):
            _state["in_decision"] = True
            try:
                return _m(*args, **kwargs)
            finally:
                _state["in_decision"] = False

        setattr(scheduler, name, wrapped)
    return scheduler


@pytest.mark.parametrize("algo", ALL)
def test_scheduler_never_reads_actual_duration_or_future(algo, default_specs, monkeypatch):
    monkeypatch.setattr(engine_mod, "Worker", SpyWorker)
    _state["violations"].clear()
    base = generate_workload(WorkloadConfig(num_tasks=250, seed=42, total_capacity=2.0))
    tasks = [SpyTask(**dataclasses.asdict(t)) for t in base]
    sched = _wrap_decisions(create_scheduler(algo))
    result = run_simulation(tasks, default_specs, sched)
    assert len(result.records) == 250
    assert _state["violations"] == []


def test_spy_detects_a_cheating_scheduler(default_specs, monkeypatch):
    from src.schedulers.least_loaded import LeastLoadedScheduler

    class CheatingLL(LeastLoadedScheduler):
        def select_worker(self, task, workers, now):
            _ = task.actual_duration
            return super().select_worker(task, workers, now)

    monkeypatch.setattr(engine_mod, "Worker", SpyWorker)
    _state["violations"].clear()
    tasks = [SpyTask(1, 0.0, 1.0, 2.0)]
    run_simulation(tasks, default_specs, _wrap_decisions(CheatingLL()))
    assert _state["violations"]


def test_static_scan_of_scheduler_sources():
    pattern = re.compile(r"actual_duration|current_end|(?<!estimated_)execution_time\(")
    offenders = []
    for path in SCHEDULER_DIR.glob("*.py"):
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            code = line.split("#", 1)[0]
            if pattern.search(code):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert offenders == []


def _scramble_actuals(tasks, factor_seed=99):
    import random

    rng = random.Random(factor_seed)
    return [dataclasses.replace(t, actual_duration=round(t.actual_duration * rng.uniform(0.2, 5.0), 4)) for t in tasks]


@pytest.mark.parametrize("algo", ["round_robin", "weighted_round_robin"])
def test_rr_wrr_assignments_independent_of_actuals(algo, workload_100, default_specs):
    a = run_simulation(workload_100, default_specs, create_scheduler(algo))
    b = run_simulation(_scramble_actuals(workload_100), default_specs, create_scheduler(algo))
    assert [(d["task_id"], d["worker_id"]) for d in a.decision_log] == [(d["task_id"], d["worker_id"]) for d in b.decision_log]


@pytest.mark.parametrize("algo", ALL)
def test_decisions_before_any_completion_independent_of_actuals(algo, default_specs):
    # All 30 tasks arrive at t=0: every decision at t=0 precedes any completion,
    # so it can depend only on estimates.
    tasks = [dataclasses.replace(t, arrival_time=0.0)
             for t in generate_workload(WorkloadConfig(num_tasks=30, seed=11, total_capacity=2.0))]
    a = run_simulation(tasks, default_specs, create_scheduler(algo))
    b = run_simulation(_scramble_actuals(tasks), default_specs, create_scheduler(algo))
    at_zero = lambda r: [(d["task_id"], d["worker_id"]) for d in r.decision_log if d["time"] == 0.0]
    assert at_zero(a) == at_zero(b)
    assert len(at_zero(a)) > 0


def test_sjf_order_independent_of_actuals_single_worker():
    # Single worker, all tasks present at t=0: SJF start order must be by estimate only.
    tasks = [dataclasses.replace(t, arrival_time=0.0)
             for t in generate_workload(WorkloadConfig(num_tasks=40, seed=3, total_capacity=1.0))]
    from src.worker import WorkerSpec

    a = run_simulation(tasks, [WorkerSpec("W1")], create_scheduler("shortest_job_first"))
    b = run_simulation(_scramble_actuals(tasks), [WorkerSpec("W1")], create_scheduler("shortest_job_first"))
    order = lambda r: [d["task_id"] for d in r.decision_log]
    assert order(a) == order(b) == [t.task_id for t in sorted(tasks, key=lambda t: (t.estimated_duration, t.task_id))]

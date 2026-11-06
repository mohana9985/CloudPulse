import dataclasses

import pytest

from src.schedulers import (ALGORITHMS, CONTROL, CONTROL_BASELINES, PRIMARY, FCFSBaselineScheduler,
                            ShortestJobFirstScheduler, create_scheduler)
from src.simulation_engine import run_simulation
from src.worker import WorkerSpec
from src.workload_generator import WorkloadConfig, generate_workload

from .conftest import make_task
from .invariants import check_schedule

ONE = [WorkerSpec("W1")]


def _start_order(result):
    return [r.task_id for r in sorted(result.records, key=lambda r: (r.start_time, r.task_id))]


def test_is_control_not_primary():
    assert "fcfs_baseline" not in ALGORITHMS
    assert "fcfs_baseline" in CONTROL_BASELINES
    assert FCFSBaselineScheduler.role == CONTROL
    assert all(cls.role == PRIMARY for cls in ALGORITHMS.values())
    assert len(ALGORITHMS) == 4


def test_runs_in_arrival_order_ignoring_size():
    tasks = [make_task(1, 0.0, 9), make_task(2, 0.5, 1), make_task(3, 1.0, 5)]
    assert _start_order(run_simulation(tasks, ONE, FCFSBaselineScheduler())) == [1, 2, 3]


def test_simultaneous_arrivals_ordered_by_task_id():
    tasks = [make_task(3, 0.0, 1), make_task(1, 0.0, 9), make_task(2, 0.0, 5)]
    assert _start_order(run_simulation(tasks, ONE, FCFSBaselineScheduler())) == [1, 2, 3]


def test_same_worker_selection_as_sjf():
    # Equal estimates -> SJF falls back to (arrival, id) = FCFS order, so the two
    # schedules must be identical; proves worker choice is shared.
    specs = [WorkerSpec("A", 1.0), WorkerSpec("B", 0.5), WorkerSpec("C", 0.25)]
    tasks = [make_task(i, float(i // 3), 2.0) for i in range(1, 31)]
    a = run_simulation(tasks, specs, FCFSBaselineScheduler())
    b = run_simulation(tasks, specs, ShortestJobFirstScheduler())
    assert a.records == b.records
    assert FCFSBaselineScheduler.select_idle_worker is ShortestJobFirstScheduler.select_idle_worker


def test_differs_from_sjf_only_in_order():
    tasks = generate_workload(WorkloadConfig(num_tasks=200, seed=5, total_capacity=2.0))
    specs = [WorkerSpec("W1", 1.0), WorkerSpec("W2", 0.6), WorkerSpec("W3", 0.4)]
    fcfs = run_simulation(tasks, specs, FCFSBaselineScheduler())
    sjf = run_simulation(tasks, specs, ShortestJobFirstScheduler())
    assert fcfs.dispatch_mode == sjf.dispatch_mode == "central_queue"
    assert fcfs.idle_while_waiting_time == sjf.idle_while_waiting_time == 0.0
    assert fcfs.records != sjf.records


@pytest.mark.parametrize("n", [100, 250, 500])
def test_invariants(n, default_specs):
    tasks = generate_workload(WorkloadConfig(num_tasks=n, seed=42, total_capacity=2.0, target_utilisation=1.2))
    result = run_simulation(tasks, default_specs, create_scheduler("fcfs_baseline"))
    assert check_schedule(result, tasks, default_specs) == []


def test_never_uses_task_size():
    tasks = [make_task(i, 0.0, est) for i, est in enumerate([7, 1, 4, 2, 9], start=1)]
    scrambled = [dataclasses.replace(t, estimated_duration=10 - t.estimated_duration) for t in tasks]
    a = run_simulation(tasks, ONE, FCFSBaselineScheduler())
    b = run_simulation(scrambled, ONE, FCFSBaselineScheduler())
    assert [d["task_id"] for d in a.decision_log] == [d["task_id"] for d in b.decision_log] == [1, 2, 3, 4, 5]


def test_empty_and_unavailable():
    specs = [WorkerSpec("A", 2.0, available=False), WorkerSpec("B")]
    assert run_simulation([], specs, FCFSBaselineScheduler()).records == []
    r = run_simulation([make_task(i, 0.0, 1) for i in range(1, 4)], specs, FCFSBaselineScheduler())
    assert {x.worker_id for x in r.records} == {"B"}

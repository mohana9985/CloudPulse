import dataclasses

import pytest

from src.schedulers import ALGORITHMS, RoundRobinScheduler, create_scheduler
from src.simulation_engine import SimulationEngine, run_simulation
from src.worker import WorkerSpec
from src.workload_generator import Task

from .conftest import make_task

ALL = sorted(ALGORITHMS)


@pytest.mark.parametrize("algo", ALL)
def test_every_task_completed_exactly_once(algo, workload_100, default_specs):
    result = run_simulation(workload_100, default_specs, create_scheduler(algo))
    ids = [r.task_id for r in result.records]
    assert len(ids) == len(set(ids)) == 100
    assert set(ids) == {t.task_id for t in workload_100}
    assert sum(w.tasks_completed for w in result.workers) == 100
    completed = [i for w in result.workers for i in w.completed_task_ids]
    assert sorted(completed) == sorted(ids)


@pytest.mark.parametrize("algo", ALL)
def test_timing_invariants(algo, workload_100, default_specs):
    result = run_simulation(workload_100, default_specs, create_scheduler(algo))
    cap = {s.worker_id: s.capacity for s in default_specs}
    for r in result.records:
        assert r.start_time >= r.arrival_time
        assert r.execution_time == pytest.approx(r.actual_duration / cap[r.worker_id])
        assert r.completion_time == pytest.approx(r.start_time + r.execution_time)
    assert result.makespan == max(r.completion_time for r in result.records)


@pytest.mark.parametrize("algo", ALL)
def test_worker_runs_one_task_at_a_time(algo, workload_100, default_specs):
    result = run_simulation(workload_100, default_specs, create_scheduler(algo))
    for wid in {s.worker_id for s in default_specs}:
        spans = sorted((r.start_time, r.completion_time) for r in result.records if r.worker_id == wid)
        for (_, end), (start, _) in zip(spans, spans[1:]):
            assert start >= end - 1e-9


@pytest.mark.parametrize("algo", ALL)
def test_deterministic_repeat_runs(algo, workload_100, default_specs):
    a = run_simulation(workload_100, default_specs, create_scheduler(algo))
    b = run_simulation(workload_100, default_specs, create_scheduler(algo))
    assert a.records == b.records
    assert a.decision_log == b.decision_log


def test_same_engine_instance_reusable_without_state_leak(workload_100, default_specs):
    engine = SimulationEngine(default_specs, RoundRobinScheduler())
    assert engine.run(workload_100).records == engine.run(workload_100).records


def test_workload_not_mutated_across_algorithms(workload_100, default_specs):
    snapshot = [dataclasses.astuple(t) for t in workload_100]
    for algo in ALL:
        run_simulation(workload_100, default_specs, create_scheduler(algo))
    assert [dataclasses.astuple(t) for t in workload_100] == snapshot


def test_total_work_identical_across_algorithms(workload_100, default_specs):
    totals = set()
    for algo in ALL:
        result = run_simulation(workload_100, default_specs, create_scheduler(algo))
        totals.add(round(sum(r.actual_duration for r in result.records), 6))
        assert {r.arrival_time for r in result.records} == {t.arrival_time for t in workload_100}
    assert len(totals) == 1


@pytest.mark.parametrize("algo", ALL)
def test_empty_workload(algo, default_specs):
    result = run_simulation([], default_specs, create_scheduler(algo))
    assert result.records == [] and result.makespan == 0.0


@pytest.mark.parametrize("algo", ALL)
def test_simultaneous_equal_tasks(algo, default_specs):
    tasks = [make_task(i, 5.0, 2.0) for i in range(1, 10)]
    result = run_simulation(tasks, default_specs, create_scheduler(algo))
    assert sorted(r.task_id for r in result.records) == list(range(1, 10))
    assert all(r.start_time >= 5.0 for r in result.records)


def test_single_worker_fifo_for_queue_algorithms():
    tasks = [make_task(1, 0.0, 5), make_task(2, 0.1, 1), make_task(3, 0.2, 3)]
    for algo in ("round_robin", "weighted_round_robin", "least_loaded"):
        result = run_simulation(tasks, [WorkerSpec("W1")], create_scheduler(algo))
        order = [r.task_id for r in sorted(result.records, key=lambda r: r.start_time)]
        assert order == [1, 2, 3], algo


def test_completion_before_arrival_at_same_instant():
    tasks = [make_task(1, 0.0, 2), make_task(2, 2.0, 1)]
    result = run_simulation(tasks, [WorkerSpec("W1")], RoundRobinScheduler())
    assert result.records[1].start_time == 2.0
    assert result.records[1].waiting_time == 0.0


def test_unsorted_input_handled():
    tasks = [make_task(3, 2.0, 1), make_task(1, 0.0, 1), make_task(2, 1.0, 1)]
    result = run_simulation(tasks, [WorkerSpec("W1")], RoundRobinScheduler())
    assert [d["task_id"] for d in result.decision_log] == [1, 2, 3]


def test_duplicate_task_ids_rejected(default_specs):
    with pytest.raises(ValueError, match="Duplicate task_id"):
        run_simulation([make_task(1), make_task(1)], default_specs, RoundRobinScheduler())


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf")])
def test_invalid_task_duration_rejected(bad):
    with pytest.raises(ValueError):
        Task(1, 0.0, bad, 1.0)
    with pytest.raises(ValueError):
        Task(1, 0.0, 1.0, bad)


def test_negative_arrival_rejected():
    with pytest.raises(ValueError):
        Task(1, -1.0, 1.0, 1.0)


def test_no_available_worker_rejected():
    with pytest.raises(ValueError, match="available"):
        SimulationEngine([WorkerSpec("W1", available=False)], RoundRobinScheduler())


def test_no_workers_rejected():
    with pytest.raises(ValueError):
        SimulationEngine([], RoundRobinScheduler())


def test_duplicate_worker_ids_rejected():
    with pytest.raises(ValueError, match="Duplicate worker_id"):
        SimulationEngine([WorkerSpec("W1"), WorkerSpec("W1")], RoundRobinScheduler())


@pytest.mark.parametrize("cap", [0, -1, float("nan")])
def test_invalid_capacity_rejected(cap):
    with pytest.raises(ValueError):
        WorkerSpec("W1", capacity=cap)


def test_invalid_max_queue_length_rejected():
    with pytest.raises(ValueError):
        WorkerSpec("W1", max_queue_length=0)


def test_unknown_algorithm_rejected():
    with pytest.raises(ValueError, match="Unknown algorithm"):
        create_scheduler("fifo")

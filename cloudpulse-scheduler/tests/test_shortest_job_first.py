import pytest

from src.schedulers import ShortestJobFirstScheduler
from src.simulation_engine import run_simulation
from src.worker import WorkerSpec

from .conftest import make_task

ONE = [WorkerSpec("W1")]


def _start_order(result):
    return [r.task_id for r in sorted(result.records, key=lambda r: (r.start_time, r.task_id))]


def test_runs_shortest_first_among_simultaneous_arrivals():
    tasks = [make_task(1, 0.0, 5), make_task(2, 0.0, 1), make_task(3, 0.0, 3)]
    result = run_simulation(tasks, ONE, ShortestJobFirstScheduler())
    assert _start_order(result) == [2, 3, 1]


def test_non_preemptive():
    tasks = [make_task(1, 0.0, 10), make_task(2, 1.0, 1)]
    result = run_simulation(tasks, ONE, ShortestJobFirstScheduler())
    rec = {r.task_id: r for r in result.records}
    assert rec[1].start_time == 0.0 and rec[1].completion_time == 10.0
    assert rec[2].start_time == 10.0
    assert rec[2].waiting_time == pytest.approx(9.0)


def test_queue_reordered_while_worker_busy():
    tasks = [make_task(1, 0.0, 4), make_task(2, 1.0, 9), make_task(3, 2.0, 2), make_task(4, 3.0, 5)]
    result = run_simulation(tasks, ONE, ShortestJobFirstScheduler())
    assert _start_order(result) == [1, 3, 4, 2]


def test_tie_break_by_arrival_then_task_id():
    tasks = [
        make_task(5, 0.0, 9),
        make_task(4, 2.0, 3),
        make_task(2, 1.0, 3),   # same estimate, earlier arrival
        make_task(3, 1.0, 3),   # same estimate & arrival, higher id
    ]
    result = run_simulation(tasks, ONE, ShortestJobFirstScheduler())
    assert _start_order(result) == [5, 2, 3, 4]


def test_orders_by_estimate_not_actual():
    tasks = [make_task(1, 0.0, est=2, actual=20), make_task(2, 0.0, est=3, actual=1)]
    result = run_simulation(tasks, ONE, ShortestJobFirstScheduler())
    assert _start_order(result) == [1, 2]


def test_dispatches_to_fastest_idle_worker(default_specs):
    tasks = [make_task(1, 0.0, 6), make_task(2, 0.0, 3), make_task(3, 0.0, 9)]
    result = run_simulation(tasks, default_specs, ShortestJobFirstScheduler())
    rec = {r.task_id: r.worker_id for r in result.records}
    assert rec == {2: "W1", 1: "W2", 3: "W3"}


def test_equal_capacity_tie_breaks_to_lowest_index():
    specs = [WorkerSpec("A"), WorkerSpec("B")]
    result = run_simulation([make_task(1, 0.0, 2)], specs, ShortestJobFirstScheduler())
    assert result.records[0].worker_id == "A"


def test_records_waiting_and_execution_time():
    specs = [WorkerSpec("W1", capacity=0.5)]
    tasks = [make_task(1, 0.0, 2), make_task(2, 0.0, 4)]
    result = run_simulation(tasks, specs, ShortestJobFirstScheduler())
    rec = {r.task_id: r for r in result.records}
    assert rec[1].execution_time == pytest.approx(4.0)
    assert rec[2].waiting_time == pytest.approx(4.0)
    assert rec[2].execution_time == pytest.approx(8.0)


def test_unavailable_worker_never_used():
    specs = [WorkerSpec("W1", capacity=2.0, available=False), WorkerSpec("W2")]
    tasks = [make_task(i, 0.0, 1) for i in range(1, 5)]
    result = run_simulation(tasks, specs, ShortestJobFirstScheduler())
    assert {r.worker_id for r in result.records} == {"W2"}

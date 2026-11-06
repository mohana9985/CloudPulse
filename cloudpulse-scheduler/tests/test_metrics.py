import pytest

from src.metrics import compute_metrics
from src.schedulers import ALGORITHMS, RoundRobinScheduler, create_scheduler
from src.simulation_engine import run_simulation
from src.worker import WorkerSpec

from .conftest import make_task


def test_hand_computed_single_worker():
    # T1: arrive 0, run 0-2.  T2: arrive 1, wait 1, run 2-5.
    tasks = [make_task(1, 0.0, 2), make_task(2, 1.0, 3)]
    m = compute_metrics(run_simulation(tasks, [WorkerSpec("W1")], RoundRobinScheduler()))
    assert m["tasks_completed"] == 2
    assert m["avg_waiting_time"] == pytest.approx(0.5)
    assert m["avg_response_time"] == pytest.approx(0.5)
    assert m["max_waiting_time"] == pytest.approx(1.0)
    assert m["avg_turnaround_time"] == pytest.approx(3.0)  # (2 + 4) / 2
    assert m["makespan"] == pytest.approx(5.0)
    assert m["throughput"] == pytest.approx(0.4)
    assert m["avg_worker_utilisation_pct"] == pytest.approx(100.0)


def test_utilisation_with_idle_gap():
    tasks = [make_task(1, 0.0, 1), make_task(2, 4.0, 1)]
    m = compute_metrics(run_simulation(tasks, [WorkerSpec("W1")], RoundRobinScheduler()))
    assert m["makespan"] == pytest.approx(5.0)
    assert m["avg_worker_utilisation_pct"] == pytest.approx(40.0)


def test_capacity_scales_execution_and_utilisation():
    tasks = [make_task(1, 0.0, 2)]
    m = compute_metrics(run_simulation(tasks, [WorkerSpec("W1", capacity=0.5)], RoundRobinScheduler()))
    assert m["makespan"] == pytest.approx(4.0)
    assert m["avg_turnaround_time"] == pytest.approx(4.0)


def test_unavailable_workers_excluded_from_utilisation():
    specs = [WorkerSpec("W1"), WorkerSpec("W2", available=False)]
    m = compute_metrics(run_simulation([make_task(1, 0.0, 2)], specs, RoundRobinScheduler()))
    assert m["avg_worker_utilisation_pct"] == pytest.approx(100.0)
    assert m["per_worker"][1]["utilisation_pct"] == 0.0


def test_per_worker_shares_sum_to_100(workload_100, default_specs):
    for algo in ALGORITHMS:
        m = compute_metrics(run_simulation(workload_100, default_specs, create_scheduler(algo)))
        assert sum(p["task_share_pct"] for p in m["per_worker"]) == pytest.approx(100.0)
        assert sum(p["work_share_pct"] for p in m["per_worker"]) == pytest.approx(100.0)
        assert sum(p["tasks_completed"] for p in m["per_worker"]) == 100


def test_imbalance_zero_when_even():
    specs = [WorkerSpec("A"), WorkerSpec("B")]
    tasks = [make_task(1, 0.0, 3), make_task(2, 0.0, 3)]
    m = compute_metrics(run_simulation(tasks, specs, RoundRobinScheduler()))
    assert m["utilisation_imbalance_cv"] == pytest.approx(0.0)


@pytest.mark.parametrize("algo", sorted(ALGORITHMS))
def test_empty_workload_returns_zeros(algo, default_specs):
    m = compute_metrics(run_simulation([], default_specs, create_scheduler(algo)))
    for key in ("tasks_completed", "avg_waiting_time", "avg_turnaround_time", "avg_response_time",
                "max_waiting_time", "makespan", "throughput", "avg_worker_utilisation_pct",
                "utilisation_imbalance_cv", "avg_queue_length"):
        assert m[key] == 0, key

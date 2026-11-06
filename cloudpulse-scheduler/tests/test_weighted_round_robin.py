from collections import Counter

import pytest

from src.schedulers import WeightedRoundRobinScheduler
from src.simulation_engine import run_simulation
from src.worker import WorkerSpec

from .conftest import make_task, make_workers


def _assigned(result):
    return [d["worker_id"] for d in result.decision_log]


def test_smooth_interleaved_sequence_for_5_3_2(default_specs):
    tasks = [make_task(i, 0.0, 1.0) for i in range(1, 11)]
    result = run_simulation(tasks, default_specs, WeightedRoundRobinScheduler())
    assert _assigned(result) == ["W1", "W2", "W3", "W1", "W1", "W2", "W1", "W3", "W2", "W1"]


def test_distribution_proportional_to_weights(default_specs):
    tasks = [make_task(i, 0.0, 1.0) for i in range(1, 101)]
    result = run_simulation(tasks, default_specs, WeightedRoundRobinScheduler())
    assert Counter(_assigned(result)) == {"W1": 50, "W2": 30, "W3": 20}


def test_weights_are_configurable_via_override(default_specs):
    tasks = [make_task(i, 0.0, 1.0) for i in range(1, 13)]
    sched = WeightedRoundRobinScheduler(weights={"W1": 1, "W2": 1, "W3": 2})
    result = run_simulation(tasks, default_specs, sched)
    assert Counter(_assigned(result)) == {"W1": 3, "W2": 3, "W3": 6}


def test_weights_from_worker_spec():
    specs = [WorkerSpec("A", weight=1), WorkerSpec("B", weight=3)]
    tasks = [make_task(i, 0.0, 1.0) for i in range(1, 9)]
    result = run_simulation(tasks, specs, WeightedRoundRobinScheduler())
    assert Counter(_assigned(result)) == {"A": 2, "B": 6}


@pytest.mark.parametrize("bad", [0, -1, 2.5, "3", True, None])
def test_invalid_weight_in_spec_rejected(bad):
    with pytest.raises(ValueError):
        WorkerSpec("W1", weight=bad)


@pytest.mark.parametrize("bad", [0, -2, 1.5])
def test_invalid_weight_override_rejected(default_specs, bad):
    with pytest.raises(ValueError):
        run_simulation([make_task(1)], default_specs, WeightedRoundRobinScheduler(weights={"W1": bad}))


def test_override_for_unknown_worker_rejected(default_specs):
    with pytest.raises(ValueError, match="unknown"):
        run_simulation([make_task(1)], default_specs, WeightedRoundRobinScheduler(weights={"W9": 2}))


def test_unavailable_worker_excluded_and_ratio_kept():
    specs = [WorkerSpec("W1", weight=5), WorkerSpec("W2", weight=3, available=False), WorkerSpec("W3", weight=2)]
    tasks = [make_task(i, 0.0, 1.0) for i in range(1, 15)]
    result = run_simulation(tasks, specs, WeightedRoundRobinScheduler())
    assert Counter(_assigned(result)) == {"W1": 10, "W3": 4}


def test_full_worker_skipped():
    w1, w2 = make_workers(WorkerSpec("W1", weight=5, max_queue_length=1), WorkerSpec("W2", weight=1))
    w1.enqueue(make_task(99))
    sched = WeightedRoundRobinScheduler()
    sched.reset([w1, w2])
    assert sched.select_worker(make_task(1), [w1, w2], 0.0).worker_id == "W2"

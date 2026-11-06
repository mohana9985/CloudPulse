import pytest

from src.schedulers import LeastLoadedScheduler
from src.simulation_engine import run_simulation
from src.worker import WorkerSpec

from .conftest import make_task, make_workers


def _setup(*specs):
    workers = make_workers(*specs)
    sched = LeastLoadedScheduler()
    sched.reset(workers)
    return workers, sched


def test_picks_lowest_queued_load():
    (w1, w2, w3), ll = _setup(WorkerSpec("W1"), WorkerSpec("W2"), WorkerSpec("W3"))
    w1.enqueue(make_task(91, est=5))
    w2.enqueue(make_task(92, est=2))
    w3.enqueue(make_task(93, est=8))
    assert ll.select_worker(make_task(1), [w1, w2, w3], 0.0) is w2


def test_load_is_capacity_adjusted():
    # W1: 10 units at cap 1.0 -> 10 s.  W2: 4 units at cap 0.5 -> 8 s.  W2 wins.
    (w1, w2), ll = _setup(WorkerSpec("W1", capacity=1.0), WorkerSpec("W2", capacity=0.5))
    w1.enqueue(make_task(91, est=10))
    w2.enqueue(make_task(92, est=4))
    assert w1.estimated_load(0.0) == pytest.approx(10.0)
    assert w2.estimated_load(0.0) == pytest.approx(8.0)
    assert ll.select_worker(make_task(1), [w1, w2], 0.0) is w2


def test_load_counts_running_remainder_plus_queue():
    (w1, w2), ll = _setup(WorkerSpec("W1"), WorkerSpec("W2"))
    w1.start(make_task(91, est=10), now=0.0)  # at t=6, 4 s left
    w1.enqueue(make_task(92, est=3))           # +3  -> 7
    w2.enqueue(make_task(93, est=7.5))         # 7.5
    assert w1.estimated_load(6.0) == pytest.approx(7.0)
    assert ll.select_worker(make_task(1), [w1, w2], 6.0) is w1


def test_running_task_over_estimate_counts_as_zero():
    (w1,), _ = _setup(WorkerSpec("W1"))
    w1.start(make_task(91, est=2, actual=10), now=0.0)
    assert w1.estimated_load(5.0) == 0.0


def test_tie_breaks_to_lowest_config_index():
    (w1, w2, w3), ll = _setup(WorkerSpec("W1"), WorkerSpec("W2"), WorkerSpec("W3"))
    w1.enqueue(make_task(91, est=4))
    # W2 and W3 both empty -> W2 (earlier in config)
    assert ll.select_worker(make_task(1), [w1, w2, w3], 0.0) is w2


def test_decision_log_records_before_and_after():
    (w1, w2), ll = _setup(WorkerSpec("W1"), WorkerSpec("W2", capacity=0.5))
    w1.enqueue(make_task(91, est=3))
    ll.select_worker(make_task(1, est=2), [w1, w2], 0.0)
    entry = ll.decision_log[-1]
    assert entry["worker_id"] == "W2"
    assert entry["loads_before"] == {"W1": pytest.approx(3.0), "W2": 0.0}
    assert entry["load_after"] == pytest.approx(4.0)  # 2 units / 0.5 capacity


def test_uses_estimate_not_actual():
    (w1, w2), ll = _setup(WorkerSpec("W1"), WorkerSpec("W2"))
    w1.enqueue(make_task(91, est=1, actual=50))  # looks light, is heavy
    w2.enqueue(make_task(92, est=5, actual=5))
    assert ll.select_worker(make_task(1), [w1, w2], 0.0) is w1


def test_skips_unavailable_worker():
    specs = [WorkerSpec("W1", available=False), WorkerSpec("W2"), WorkerSpec("W3")]
    tasks = [make_task(i, 0.0, 1.0) for i in range(1, 7)]
    result = run_simulation(tasks, specs, LeastLoadedScheduler())
    assert result.workers[0].tasks_completed == 0
    assert {d["worker_id"] for d in result.decision_log} == {"W2", "W3"}


def test_balances_heterogeneous_workers_in_simulation(default_specs):
    tasks = [make_task(i, 0.0, 6.0) for i in range(1, 21)]
    result = run_simulation(tasks, default_specs, LeastLoadedScheduler())
    counts = [w.tasks_completed for w in result.workers]
    assert counts[0] > counts[1] > counts[2]
    assert sum(counts) == 20

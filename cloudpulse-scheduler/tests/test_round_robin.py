from src.schedulers import RoundRobinScheduler
from src.simulation_engine import run_simulation
from src.worker import WorkerSpec

from .conftest import make_task, make_workers


def _assigned(result):
    return [d["worker_id"] for d in result.decision_log]


def test_cyclic_assignment_order(default_specs):
    tasks = [make_task(i, 0.0, 2.0) for i in range(1, 8)]
    result = run_simulation(tasks, default_specs, RoundRobinScheduler())
    assert _assigned(result) == ["W1", "W2", "W3", "W1", "W2", "W3", "W1"]
    assert [d["task_id"] for d in result.decision_log] == list(range(1, 8))


def test_even_task_count_ignores_capacity(default_specs):
    tasks = [make_task(i, float(i), 1.0) for i in range(1, 31)]
    result = run_simulation(tasks, default_specs, RoundRobinScheduler())
    counts = {w.worker_id: w.tasks_completed for w in result.workers}
    assert counts == {"W1": 10, "W2": 10, "W3": 10}


def test_skips_unavailable_worker():
    specs = [WorkerSpec("W1"), WorkerSpec("W2", available=False), WorkerSpec("W3")]
    tasks = [make_task(i, 0.0, 1.0) for i in range(1, 5)]
    result = run_simulation(tasks, specs, RoundRobinScheduler())
    assert _assigned(result) == ["W1", "W3", "W1", "W3"]
    assert result.workers[1].tasks_completed == 0


def test_skips_full_worker_and_keeps_rotation():
    w1, w2, w3 = make_workers(WorkerSpec("W1"), WorkerSpec("W2", max_queue_length=1), WorkerSpec("W3"))
    w2.enqueue(make_task(99))
    rr = RoundRobinScheduler()
    rr.reset([w1, w2, w3])
    picks = [rr.select_worker(make_task(i), [w1, w2, w3], 0.0).worker_id for i in range(1, 4)]
    assert picks == ["W1", "W3", "W1"]
    assert rr.decision_log[1]["skipped"] == 1


def test_returns_none_when_no_worker_can_accept():
    w1, w2 = make_workers(WorkerSpec("W1", max_queue_length=1), WorkerSpec("W2", available=False))
    w1.enqueue(make_task(99))
    rr = RoundRobinScheduler()
    rr.reset([w1, w2])
    assert rr.select_worker(make_task(1), [w1, w2], 0.0) is None


def test_backlog_when_queues_full_still_completes_all():
    specs = [WorkerSpec("W1", max_queue_length=1), WorkerSpec("W2", max_queue_length=1)]
    tasks = [make_task(i, 0.0, 1.0) for i in range(1, 11)]
    result = run_simulation(tasks, specs, RoundRobinScheduler())
    assert sorted(r.task_id for r in result.records) == list(range(1, 11))
    assert result.peak_queue_length == 8

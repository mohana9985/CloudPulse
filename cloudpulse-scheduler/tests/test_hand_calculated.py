import pytest

from src.metrics import compute_metrics
from src.schedulers import create_scheduler
from src.simulation_engine import run_simulation
from src.worker import WorkerSpec

from .conftest import make_task

SPECS = [WorkerSpec("A", capacity=1.0, weight=2), WorkerSpec("B", capacity=0.5, weight=1)]
TASKS = [make_task(1, 0, 4), make_task(2, 0, 2), make_task(3, 1, 1), make_task(4, 2, 3)]

# algorithm -> ({task: (worker, start, end)}, expected metrics)
EXPECTED = {
    # RR: T1->A, T2->B, T3->A, T4->B.  A: T1 0-4, T3 4-5.  B: T2 0-4, T4 4-10.
    "round_robin": (
        {1: ("A", 0, 4), 2: ("B", 0, 4), 3: ("A", 4, 5), 4: ("B", 4, 10)},
        dict(avg_waiting_time=1.25, max_waiting_time=3, avg_turnaround_time=5.0, makespan=10,
             throughput=0.4, avg_worker_utilisation_pct=75.0),  # A 5/10, B 10/10
    ),
    # WRR 2:1 smooth: A, B, A, A.  A: T1 0-4, T3 4-5, T4 5-8.  B: T2 0-4.
    "weighted_round_robin": (
        {1: ("A", 0, 4), 2: ("B", 0, 4), 3: ("A", 4, 5), 4: ("A", 5, 8)},
        dict(avg_waiting_time=1.5, max_waiting_time=3, avg_turnaround_time=4.5, makespan=8,
             throughput=0.5, avg_worker_utilisation_pct=75.0),  # A 8/8, B 4/8
    ),
    # LL: t0 T1 tie->A; T2 A=4,B=0 ->B.  t1 T3: A rem 3, B rem 3 tie ->A.
    #     t2 T4: A rem 2 + 1 = 3, B rem 2 -> B.  Same schedule as RR.
    "least_loaded": (
        {1: ("A", 0, 4), 2: ("B", 0, 4), 3: ("A", 4, 5), 4: ("B", 4, 10)},
        dict(avg_waiting_time=1.25, max_waiting_time=3, avg_turnaround_time=5.0, makespan=10,
             throughput=0.4, avg_worker_utilisation_pct=75.0),
    ),
    # SJF: t0 queue {T2(2), T1(4)}: fastest A takes T2 0-2, B takes T1 0-8.
    #      t2 A free, queue {T3(1), T4(3)} -> T3 2-3, then T4 3-6.
    "shortest_job_first": (
        {1: ("B", 0, 8), 2: ("A", 0, 2), 3: ("A", 2, 3), 4: ("A", 3, 6)},
        dict(avg_waiting_time=0.5, max_waiting_time=1, avg_turnaround_time=4.0, makespan=8,
             throughput=0.5, avg_worker_utilisation_pct=87.5),  # A 6/8, B 8/8
    ),
    # FCFS control: t0 queue [T1, T2]: fastest A takes T1 0-4, B takes T2 0-4.
    #   t4 both free, queue [T3, T4]: A (fastest) takes T3 4-5, B takes T4 4-10.
    "fcfs_baseline": (
        {1: ("A", 0, 4), 2: ("B", 0, 4), 3: ("A", 4, 5), 4: ("B", 4, 10)},
        dict(avg_waiting_time=1.25, max_waiting_time=3, avg_turnaround_time=5.0, makespan=10,
             throughput=0.4, avg_worker_utilisation_pct=75.0),
    ),
}


@pytest.mark.parametrize("algo", sorted(EXPECTED))
def test_trace_and_metrics_match_hand_calculation(algo):
    result = run_simulation(TASKS, SPECS, create_scheduler(algo))
    schedule, metrics = EXPECTED[algo]
    got = {r.task_id: (r.worker_id, r.start_time, r.completion_time) for r in result.records}
    assert got == {k: (w, pytest.approx(s), pytest.approx(e)) for k, (w, s, e) in schedule.items()}
    m = compute_metrics(result)
    for key, value in metrics.items():
        assert m[key] == pytest.approx(value), key
    assert m["avg_response_time"] == pytest.approx(metrics["avg_waiting_time"])


def test_least_loaded_logged_loads_match_hand_calculation():
    result = run_simulation(TASKS, SPECS, create_scheduler("least_loaded"))
    log = {d["task_id"]: d for d in result.decision_log}
    assert log[1]["loads_before"] == {"A": 0.0, "B": 0.0}
    assert log[2]["loads_before"] == {"A": pytest.approx(4.0), "B": 0.0}
    assert log[3]["loads_before"] == {"A": pytest.approx(3.0), "B": pytest.approx(3.0)}
    assert log[4]["loads_before"] == {"A": pytest.approx(3.0), "B": pytest.approx(2.0)}
    assert log[4]["load_after"] == pytest.approx(8.0)  # 2 + 3/0.5


def test_round_robin_queue_length_by_hand():
    # pending (arrived, not started): [1,2) -> 1 (T3), [2,4) -> 2 (T3,T4), else 0.
    result = run_simulation(TASKS, SPECS, create_scheduler("round_robin"))
    assert result.peak_queue_length == 2
    assert result.avg_queue_length == pytest.approx((1 * 1 + 2 * 2) / 10)


def test_idle_while_waiting_by_hand():
    # Two equal workers; RR puts T1(10) and T3(1) on A, T2(1) on B.
    # B is free from t=1 while T3 waits behind T1 on A until t=10 -> 9 worker-seconds.
    specs = [WorkerSpec("A"), WorkerSpec("B")]
    tasks = [make_task(1, 0, 10), make_task(2, 0, 1), make_task(3, 0, 1)]
    rr = run_simulation(tasks, specs, create_scheduler("round_robin"))
    assert rr.idle_while_waiting_time == pytest.approx(9.0)
    sjf = run_simulation(tasks, specs, create_scheduler("shortest_job_first"))
    assert sjf.idle_while_waiting_time == 0.0


def test_sjf_heterogeneous_with_misestimate():
    # T1 looks short (est 1) but is long (actual 6); T2 est 2 / actual 2; T3 est 3 / actual 3.
    # t0: fastest idle A gets min-est T1 -> runs 0-6 on A.  B gets T2 -> 2/0.5 = 4 s, 0-4.
    # t4: B free, takes T3 -> 3/0.5 = 6 s, 4-10.
    specs = [WorkerSpec("A", capacity=1.0), WorkerSpec("B", capacity=0.5)]
    tasks = [make_task(1, 0, est=1, actual=6), make_task(2, 0, est=2, actual=2), make_task(3, 0, est=3, actual=3)]
    result = run_simulation(tasks, specs, create_scheduler("shortest_job_first"))
    got = {r.task_id: (r.worker_id, r.start_time, r.completion_time) for r in result.records}
    assert got == {1: ("A", 0, 6), 2: ("B", 0, 4), 3: ("B", 4, 10)}
    assert [d["task_id"] for d in result.decision_log] == [1, 2, 3]


def test_sjf_is_non_delay_greedy_on_heterogeneous_workers():
    # Known limitation: SJF never leaves a worker idle while work waits, even if
    # waiting for a faster worker would finish sooner.
    # T1 (1.5) -> A at t=0, A busy until 1.5.  T2 (4) arrives t=1, B idle -> B runs it 1-9.
    # Waiting for A would have finished T2 at 5.5.
    specs = [WorkerSpec("A", capacity=1.0), WorkerSpec("B", capacity=0.5)]
    tasks = [make_task(1, 0, 1.5), make_task(2, 1, 4)]
    result = run_simulation(tasks, specs, create_scheduler("shortest_job_first"))
    rec = {r.task_id: r for r in result.records}
    assert (rec[1].worker_id, rec[1].completion_time) == ("A", 1.5)
    assert (rec[2].worker_id, rec[2].start_time, rec[2].completion_time) == ("B", 1.0, 9.0)

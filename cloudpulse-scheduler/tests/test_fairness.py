import dataclasses
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.experiment import run_comparison
from src.metrics import compute_metrics
from src.schedulers import ALGORITHMS, create_scheduler
from src.simulation_engine import run_simulation
from src.worker import WorkerSpec, specs_fingerprint
from src.workload_generator import WorkloadConfig, generate_workload, workload_fingerprint

from .invariants import check_schedule, reference_metrics

ALL = sorted(ALGORITHMS)
ROOT = Path(__file__).resolve().parent.parent


def _digest(result) -> str:
    payload = [dataclasses.astuple(r) for r in result.records]
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


def test_comparison_feeds_identical_inputs(workload_100, default_specs):
    results = run_comparison(workload_100, default_specs)
    assert set(results) == set(ALL)
    assert {r.workload_fingerprint for r in results.values()} == {workload_fingerprint(workload_100)}
    assert {r.worker_config_fingerprint for r in results.values()} == {specs_fingerprint(default_specs)}
    for result in results.values():
        assert [w.capacity for w in result.workers] == [1.0, 0.6, 0.4]
        assert [w.weight for w in result.workers] == [5, 3, 2]
        by_id = {t.task_id: t for t in workload_100}
        for r in result.records:
            t = by_id[r.task_id]
            assert (r.arrival_time, r.estimated_duration, r.actual_duration) == (
                t.arrival_time, t.estimated_duration, t.actual_duration)


def test_fingerprint_detects_any_field_change(workload_100):
    base = workload_fingerprint(workload_100)
    t0 = workload_100[0]
    for field, value in [("arrival_time", t0.arrival_time + 1e-4), ("estimated_duration", t0.estimated_duration + 1e-4),
                         ("actual_duration", t0.actual_duration + 1e-4), ("task_type", "x")]:
        changed = [dataclasses.replace(t0, **{field: value})] + workload_100[1:]
        assert workload_fingerprint(changed) != base, field


def test_worker_fingerprint_detects_change(default_specs):
    changed = [dataclasses.replace(default_specs[0], capacity=0.9)] + default_specs[1:]
    assert specs_fingerprint(changed) != specs_fingerprint(default_specs)


def test_fresh_workers_per_run(workload_100, default_specs):
    results = run_comparison(workload_100, default_specs)
    worker_objs = [id(w) for r in results.values() for w in r.workers]
    assert len(worker_objs) == len(set(worker_objs))
    for r in results.values():
        assert sum(w.tasks_completed for w in r.workers) == 100


def test_regenerated_workload_is_identical_to_original():
    cfg = WorkloadConfig(num_tasks=500, seed=42, total_capacity=2.0)
    assert workload_fingerprint(generate_workload(cfg)) == workload_fingerprint(generate_workload(cfg))


@pytest.mark.parametrize("algo", ALL)
def test_ten_repeats_identical(algo, default_specs):
    tasks = generate_workload(WorkloadConfig(num_tasks=250, seed=42, total_capacity=2.0))
    digests = {_digest(run_simulation(tasks, default_specs, create_scheduler(algo))) for _ in range(10)}
    assert len(digests) == 1


_SUBPROCESS_SNIPPET = """
import dataclasses, hashlib, json
from src.config import load_config
from src.experiment import run_comparison
from src.workload_generator import generate_workload
wc, ws = load_config()
res = run_comparison(generate_workload(wc), ws)
print(json.dumps({k: hashlib.sha256(json.dumps([dataclasses.astuple(r) for r in v.records]).encode()).hexdigest()
                  for k, v in res.items()}, sort_keys=True))
"""


def test_deterministic_across_processes_and_hash_seeds():
    outputs = set()
    for seed in ("0", "1", "12345"):
        proc = subprocess.run(
            [sys.executable, "-c", _SUBPROCESS_SNIPPET], cwd=ROOT, capture_output=True, text=True, check=True,
            env={"PYTHONHASHSEED": seed, "PATH": ""},
        )
        outputs.add(proc.stdout.strip())
    assert len(outputs) == 1


@pytest.mark.parametrize("n", [100, 250, 500])
@pytest.mark.parametrize("algo", ALL)
def test_invariants_at_scale(n, algo, default_specs):
    tasks = generate_workload(WorkloadConfig(num_tasks=n, seed=42, total_capacity=2.0))
    result = run_simulation(tasks, default_specs, create_scheduler(algo))
    assert check_schedule(result, tasks, default_specs) == []
    assert len(result.records) == n


@pytest.mark.parametrize("n", [100, 250, 500])
@pytest.mark.parametrize("algo", ALL)
def test_metrics_match_independent_reference(n, algo, default_specs):
    tasks = generate_workload(WorkloadConfig(num_tasks=n, seed=42, total_capacity=2.0))
    result = run_simulation(tasks, default_specs, create_scheduler(algo))
    got, ref = compute_metrics(result), reference_metrics(result, default_specs)
    for key, value in ref.items():
        assert got[key] == pytest.approx(value, rel=1e-9, abs=1e-9), key
    for w in result.workers:
        span_sum = sum(r.execution_time for r in result.records if r.worker_id == w.worker_id)
        assert w.busy_time == pytest.approx(span_sum)


@pytest.mark.parametrize("seed", [1, 7, 42, 2024])
def test_invariants_multiple_seeds(seed, default_specs):
    tasks = generate_workload(WorkloadConfig(num_tasks=250, seed=seed, total_capacity=2.0))
    for algo, result in run_comparison(tasks, default_specs).items():
        assert check_schedule(result, tasks, default_specs) == [], algo


@pytest.mark.parametrize("algo", ALL)
def test_overloaded_workload_completes(algo, default_specs):
    # Offered load 150% of capacity: queues grow without bound, all must still finish.
    tasks = generate_workload(WorkloadConfig(num_tasks=500, seed=42, total_capacity=2.0, target_utilisation=1.5))
    result = run_simulation(tasks, default_specs, create_scheduler(algo))
    assert check_schedule(result, tasks, default_specs) == []
    # Backlog measured in *work*, not task count: SJF clears short tasks first,
    # so it holds fewer (but larger) tasks than the FIFO-queue algorithms.
    last_arrival = max(t.arrival_time for t in tasks)
    waiting_work = sum(r.actual_duration for r in result.records if r.start_time > last_arrival)
    assert waiting_work > 0.2 * sum(t.actual_duration for t in tasks)
    assert result.makespan > last_arrival * 1.3


@pytest.mark.parametrize("algo", ALL)
def test_overloaded_with_queue_limits_uses_backlog(algo):
    specs = [WorkerSpec("W1", 1.0, 5, max_queue_length=2), WorkerSpec("W2", 0.6, 3, max_queue_length=2),
             WorkerSpec("W3", 0.4, 2, max_queue_length=2)]
    tasks = generate_workload(WorkloadConfig(num_tasks=500, seed=3, total_capacity=2.0, target_utilisation=1.5))
    result = run_simulation(tasks, specs, create_scheduler(algo))
    assert check_schedule(result, tasks, specs) == []


@pytest.mark.parametrize("algo", ALL)
def test_unavailable_worker_at_scale(algo):
    specs = [WorkerSpec("W1", 1.0, 5), WorkerSpec("W2", 0.6, 3, available=False), WorkerSpec("W3", 0.4, 2)]
    tasks = generate_workload(WorkloadConfig(num_tasks=250, seed=42, total_capacity=1.4))
    result = run_simulation(tasks, specs, create_scheduler(algo))
    assert check_schedule(result, tasks, specs) == []
    assert result.workers[1].tasks_completed == 0 and result.workers[1].busy_time == 0


@pytest.mark.parametrize("algo", ALL)
def test_burst_of_simultaneous_arrivals(algo, default_specs):
    tasks = [dataclasses.replace(t, arrival_time=10.0)
             for t in generate_workload(WorkloadConfig(num_tasks=100, seed=5, total_capacity=2.0))]
    result = run_simulation(tasks, default_specs, create_scheduler(algo))
    assert check_schedule(result, tasks, default_specs) == []
    assert min(r.start_time for r in result.records) == 10.0


def test_idle_while_waiting_is_zero_for_sjf(workload_100, default_specs):
    results = run_comparison(workload_100, default_specs)
    assert results["shortest_job_first"].idle_while_waiting_time == 0.0
    for name in ("round_robin", "weighted_round_robin", "least_loaded"):
        assert results[name].idle_while_waiting_time >= 0.0

import pytest

from src.config import DEFAULT_CONFIG_PATH, load_config
from src.workload_generator import (
    DEFAULT_SIZE_RANGES,
    Task,
    WorkloadConfig,
    generate_workload,
    load_workload,
    save_workload,
)


def test_same_seed_same_workload():
    cfg = WorkloadConfig(num_tasks=250, seed=7)
    assert generate_workload(cfg) == generate_workload(cfg)


def test_different_seed_different_workload():
    assert generate_workload(WorkloadConfig(num_tasks=50, seed=1)) != generate_workload(WorkloadConfig(num_tasks=50, seed=2))


@pytest.mark.parametrize("n", [0, 1, 100, 250, 500])
def test_task_count_and_ids(n):
    tasks = generate_workload(WorkloadConfig(num_tasks=n))
    assert len(tasks) == n
    assert [t.task_id for t in tasks] == list(range(1, n + 1))


def test_arrivals_non_decreasing_and_sizes_in_range():
    cfg = WorkloadConfig(num_tasks=500, estimate_error=0.2)
    tasks = generate_workload(cfg)
    arrivals = [t.arrival_time for t in tasks]
    assert arrivals == sorted(arrivals)
    for t in tasks:
        lo, hi = DEFAULT_SIZE_RANGES[t.task_type]
        assert lo <= t.actual_duration <= hi
        assert 0.8 * t.actual_duration - 1e-3 <= t.estimated_duration <= 1.2 * t.actual_duration + 1e-3


def test_all_size_classes_present():
    types = {t.task_type for t in generate_workload(WorkloadConfig(num_tasks=200))}
    assert types == {"small", "medium", "large"}


def test_zero_estimate_error_means_exact_estimates():
    tasks = generate_workload(WorkloadConfig(num_tasks=50, estimate_error=0.0))
    assert all(t.estimated_duration == t.actual_duration for t in tasks)


@pytest.mark.parametrize("ext", ["csv", "json"])
def test_save_load_round_trip(tmp_path, ext):
    tasks = generate_workload(WorkloadConfig(num_tasks=100))
    path = save_workload(tasks, tmp_path / f"w.{ext}", metadata={"seed": 42})
    assert load_workload(path) == tasks


def test_load_rejects_duplicates(tmp_path):
    path = save_workload([Task(1, 0.0, 1.0, 1.0), Task(1, 1.0, 1.0, 1.0)], tmp_path / "dup.csv")
    with pytest.raises(ValueError, match="Duplicate"):
        load_workload(path)


def test_load_rejects_invalid_duration(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("task_id,arrival_time,estimated_duration,actual_duration,task_type,priority\n1,0,0,1,small,1\n")
    with pytest.raises(ValueError):
        load_workload(path)


def test_unsupported_extension(tmp_path):
    with pytest.raises(ValueError):
        save_workload([], tmp_path / "w.txt")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"num_tasks": -1},
        {"target_utilisation": 0},
        {"total_capacity": 0},
        {"estimate_error": 1.0},
        {"size_mix": {}},
        {"size_mix": {"huge": 1.0}},
        {"size_ranges": {"small": (5, 1), "medium": (5, 20), "large": (20, 60)}},
    ],
)
def test_invalid_config_rejected(kwargs):
    with pytest.raises(ValueError):
        WorkloadConfig(**kwargs)


def test_default_config_file_loads():
    workload_cfg, workers = load_config(DEFAULT_CONFIG_PATH)
    assert [w.worker_id for w in workers] == ["W1", "W2", "W3"]
    assert [w.weight for w in workers] == [5, 3, 2]
    assert workload_cfg.total_capacity == pytest.approx(2.0)
    assert workload_cfg.seed == 42

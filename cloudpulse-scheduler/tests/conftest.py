from __future__ import annotations

import pytest

from src.worker import Worker, WorkerSpec
from src.workload_generator import Task, WorkloadConfig, generate_workload


def make_task(task_id: int, arrival: float = 0.0, est: float = 1.0, actual: float | None = None, task_type: str = "small") -> Task:
    return Task(task_id, arrival, est, est if actual is None else actual, task_type)


def make_workers(*specs: WorkerSpec) -> list[Worker]:
    return [Worker(s) for s in specs]


DEFAULT_SPECS = [
    WorkerSpec("W1", capacity=1.0, weight=5),
    WorkerSpec("W2", capacity=0.6, weight=3),
    WorkerSpec("W3", capacity=0.4, weight=2),
]


@pytest.fixture
def default_specs() -> list[WorkerSpec]:
    return list(DEFAULT_SPECS)


@pytest.fixture
def workload_100() -> list[Task]:
    return generate_workload(WorkloadConfig(num_tasks=100, seed=42, total_capacity=2.0))

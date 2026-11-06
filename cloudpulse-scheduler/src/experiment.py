from __future__ import annotations

import dataclasses
from typing import Iterable, Mapping, Sequence

from .metrics import compute_metrics
from .schedulers import ALGORITHMS, ALL_CONFIGURATIONS, create_scheduler
from .simulation_engine import SimulationResult, run_simulation
from .worker import WorkerSpec, specs_fingerprint
from .workload_generator import Task, WorkloadConfig, generate_workload, validate_workload, workload_fingerprint


def run_comparison(
    tasks: Iterable[Task],
    worker_specs: Sequence[WorkerSpec],
    algorithms: Iterable[str] | None = None,
    scheduler_kwargs: Mapping[str, dict] | None = None,
) -> dict[str, SimulationResult]:
    shared_tasks = tuple(validate_workload(tasks))
    shared_specs = tuple(worker_specs)
    expected_workload = workload_fingerprint(shared_tasks)
    expected_workers = specs_fingerprint(shared_specs)
    kwargs = scheduler_kwargs or {}

    results: dict[str, SimulationResult] = {}
    for name in algorithms or ALGORITHMS:
        result = run_simulation(shared_tasks, shared_specs, create_scheduler(name, **kwargs.get(name, {})))
        if result.workload_fingerprint != expected_workload:
            raise RuntimeError(f"{name} received a different workload")
        if result.worker_config_fingerprint != expected_workers:
            raise RuntimeError(f"{name} received a different worker configuration")
        results[name] = result
    return results


@dataclasses.dataclass(frozen=True)
class GridSpec:
    sizes: tuple[int, ...] = (100, 250, 500)
    seeds: tuple[int, ...] = (42, 43, 44, 45, 46, 47, 48, 49, 50, 51)
    loads: tuple[tuple[str, float], ...] = (("underloaded", 0.5), ("nominal", 0.85), ("overloaded", 1.2))

    def __post_init__(self) -> None:
        if not self.sizes or not self.seeds or not self.loads:
            raise ValueError("Grid needs at least one size, seed and load condition")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("Grid seeds must be unique")
        if len({name for name, _ in self.loads}) != len(self.loads):
            raise ValueError("Load condition names must be unique")


def run_grid(
    base_config: WorkloadConfig,
    worker_specs: Sequence[WorkerSpec],
    grid: GridSpec,
    algorithms: Iterable[str] | None = None,
    scheduler_kwargs: Mapping[str, dict] | None = None,
) -> list[dict]:
    algos = list(algorithms or ALL_CONFIGURATIONS)
    rows: list[dict] = []
    for size in grid.sizes:
        for load_name, target in grid.loads:
            for seed in grid.seeds:
                cfg = dataclasses.replace(base_config, num_tasks=size, seed=seed, target_utilisation=target)
                tasks = generate_workload(cfg)
                for name, result in run_comparison(tasks, worker_specs, algos, scheduler_kwargs).items():
                    metrics = compute_metrics(result)
                    rows.append(
                        {
                            "workload_size": size,
                            "load_condition": load_name,
                            "target_utilisation": target,
                            "seed": seed,
                            **metrics,
                        }
                    )
    return rows

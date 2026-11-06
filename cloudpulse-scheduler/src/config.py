from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .worker import WorkerSpec
from .workload_generator import DEFAULT_SIZE_MIX, DEFAULT_SIZE_RANGES, WorkloadConfig

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "scheduler_config.yaml"


def parse_workers(raw: list[dict[str, Any]]) -> list[WorkerSpec]:
    if not raw:
        raise ValueError("Config must define at least one worker")
    return [
        WorkerSpec(
            worker_id=str(w["id"]),
            capacity=w.get("capacity", 1.0),
            weight=w.get("weight", 1),
            available=w.get("available", True),
            max_queue_length=w.get("max_queue_length"),
        )
        for w in raw
    ]


def _read(path: str | Path) -> dict:
    with Path(path).open() as fh:
        return yaml.safe_load(fh) or {}


def load_grid(path: str | Path = DEFAULT_CONFIG_PATH):
    from .experiment import GridSpec

    raw = _read(path).get("experiment", {}).get("grid")
    if not raw:
        return GridSpec()
    return GridSpec(
        sizes=tuple(int(s) for s in raw["sizes"]),
        seeds=tuple(int(s) for s in raw["seeds"]),
        loads=tuple((str(k), float(v)) for k, v in raw["loads"].items()),
    )


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> tuple[WorkloadConfig, list[WorkerSpec]]:
    data = _read(path)
    workers = parse_workers(data.get("workers", []))
    exp = data.get("experiment", {})
    wl = data.get("workload", {})
    total_capacity = sum(w.capacity for w in workers if w.available)
    workload = WorkloadConfig(
        num_tasks=int(exp.get("num_tasks", 100)),
        seed=int(exp.get("seed", 42)),
        target_utilisation=float(wl.get("target_utilisation", 0.85)),
        total_capacity=total_capacity,
        estimate_error=float(wl.get("estimate_error", 0.20)),
        size_mix=dict(wl.get("size_mix", DEFAULT_SIZE_MIX)),
        size_ranges={k: (float(v[0]), float(v[1])) for k, v in wl.get("size_ranges", DEFAULT_SIZE_RANGES).items()},
    )
    return workload, workers

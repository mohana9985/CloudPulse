# Durations are simulated seconds on a capacity-1.0 worker. Schedulers may only read
# estimated_duration; actual_duration is used by the engine alone.
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

TASK_FIELDS = (
    "task_id",
    "arrival_time",
    "estimated_duration",
    "actual_duration",
    "task_type",
    "priority",
)

DEFAULT_SIZE_MIX: dict[str, float] = {"small": 0.6, "medium": 0.3, "large": 0.1}
DEFAULT_SIZE_RANGES: dict[str, tuple[float, float]] = {
    "small": (1.0, 5.0),
    "medium": (5.0, 20.0),
    "large": (20.0, 60.0),
}
_DECIMALS = 4  # values are rounded so CSV/JSON round-trips are exact
_MIN_DURATION = 10 ** -_DECIMALS


def _is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


@dataclass(frozen=True)
class Task:
    task_id: int
    arrival_time: float
    estimated_duration: float
    actual_duration: float
    task_type: str = "medium"
    priority: int = 1  # informational only; none of the four algorithms use it

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, int) or isinstance(self.task_id, bool):
            raise ValueError(f"task_id must be an integer, got {self.task_id!r}")
        if not _is_finite_number(self.arrival_time) or self.arrival_time < 0:
            raise ValueError(f"Task {self.task_id}: arrival_time must be a finite number >= 0")
        for name in ("estimated_duration", "actual_duration"):
            value = getattr(self, name)
            if not _is_finite_number(value) or value <= 0:
                raise ValueError(f"Task {self.task_id}: {name} must be a finite number > 0, got {value!r}")


@dataclass(frozen=True)
class WorkloadConfig:
    num_tasks: int = 100
    seed: int = 42
    target_utilisation: float = 0.85
    total_capacity: float = 2.0
    estimate_error: float = 0.20
    size_mix: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_SIZE_MIX))
    size_ranges: Mapping[str, tuple[float, float]] = field(default_factory=lambda: dict(DEFAULT_SIZE_RANGES))

    def __post_init__(self) -> None:
        if not isinstance(self.num_tasks, int) or self.num_tasks < 0:
            raise ValueError("num_tasks must be an integer >= 0")
        if not _is_finite_number(self.target_utilisation) or self.target_utilisation <= 0:
            raise ValueError("target_utilisation must be > 0")
        if not _is_finite_number(self.total_capacity) or self.total_capacity <= 0:
            raise ValueError("total_capacity must be > 0")
        if not _is_finite_number(self.estimate_error) or not 0 <= self.estimate_error < 1:
            raise ValueError("estimate_error must be in [0, 1)")
        if not self.size_mix:
            raise ValueError("size_mix must not be empty")
        for task_type, prob in self.size_mix.items():
            if task_type not in self.size_ranges:
                raise ValueError(f"size_mix type {task_type!r} has no entry in size_ranges")
            if not _is_finite_number(prob) or prob < 0:
                raise ValueError(f"size_mix[{task_type!r}] must be >= 0")
        if sum(self.size_mix.values()) <= 0:
            raise ValueError("size_mix probabilities must sum to > 0")
        for task_type, bounds in self.size_ranges.items():
            lo, hi = bounds
            if not (_is_finite_number(lo) and _is_finite_number(hi)) or lo <= 0 or hi < lo:
                raise ValueError(f"size_ranges[{task_type!r}] must satisfy 0 < low <= high")

    def mean_duration(self) -> float:
        total_p = sum(self.size_mix.values())
        return sum(p * sum(self.size_ranges[t]) / 2 for t, p in self.size_mix.items()) / total_p

    def arrival_rate(self) -> float:
        return self.target_utilisation * self.total_capacity / self.mean_duration()


def generate_workload(config: WorkloadConfig) -> list[Task]:
    rng = random.Random(config.seed)
    types = list(config.size_mix)
    weights = [config.size_mix[t] for t in types]
    rate = config.arrival_rate()
    err = config.estimate_error

    tasks: list[Task] = []
    clock = 0.0
    for i in range(config.num_tasks):
        clock += rng.expovariate(rate)
        task_type = rng.choices(types, weights=weights)[0]
        lo, hi = config.size_ranges[task_type]
        actual = max(round(rng.uniform(lo, hi), _DECIMALS), _MIN_DURATION)
        estimate = max(round(actual * rng.uniform(1 - err, 1 + err), _DECIMALS), _MIN_DURATION)
        priority = rng.randint(1, 3)
        tasks.append(
            Task(
                task_id=i + 1,
                arrival_time=round(clock, _DECIMALS),
                estimated_duration=estimate,
                actual_duration=actual,
                task_type=task_type,
                priority=priority,
            )
        )
    return tasks


def validate_workload(tasks: Iterable[Task]) -> list[Task]:
    task_list = list(tasks)
    seen: set[int] = set()
    for task in task_list:
        if not isinstance(task, Task):
            raise TypeError(f"Expected Task, got {type(task).__name__}")
        if task.task_id in seen:
            raise ValueError(f"Duplicate task_id {task.task_id} in workload")
        seen.add(task.task_id)
    return task_list


def workload_fingerprint(tasks: Iterable[Task]) -> str:
    rows = [asdict(t) for t in sorted(tasks, key=lambda t: t.task_id)]
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def save_workload(tasks: Sequence[Task], path: str | Path, metadata: Mapping | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [asdict(t) for t in tasks]
    if path.suffix.lower() == ".csv":
        with path.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=TASK_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    elif path.suffix.lower() == ".json":
        with path.open("w") as fh:
            json.dump({"metadata": dict(metadata or {}), "tasks": rows}, fh, indent=2)
    else:
        raise ValueError(f"Unsupported workload format {path.suffix!r}; use .csv or .json")
    return path


def _task_from_mapping(row: Mapping) -> Task:
    try:
        return Task(
            task_id=int(row["task_id"]),
            arrival_time=float(row["arrival_time"]),
            estimated_duration=float(row["estimated_duration"]),
            actual_duration=float(row["actual_duration"]),
            task_type=str(row.get("task_type", "medium")),
            priority=int(row.get("priority", 1)),
        )
    except KeyError as exc:
        raise ValueError(f"Workload row missing field {exc}") from exc


def load_workload(path: str | Path) -> list[Task]:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(newline="") as fh:
            tasks = [_task_from_mapping(row) for row in csv.DictReader(fh)]
    elif path.suffix.lower() == ".json":
        with path.open() as fh:
            data = json.load(fh)
        rows = data["tasks"] if isinstance(data, dict) else data
        tasks = [_task_from_mapping(row) for row in rows]
    else:
        raise ValueError(f"Unsupported workload format {path.suffix!r}; use .csv or .json")
    return validate_workload(tasks)

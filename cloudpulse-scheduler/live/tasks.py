# Each task is deterministic: the same (type, units) always returns the same checksum,
# so results can be verified. "units" scales the amount of CPU work linearly.
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Callable

# Reference seconds of CPU per unit on a capacity-1.0 worker (W1). Measured with
# `python -m live.calibrate` inside the W1 container (0.75 CPU quota, Colima on an
# Apple M1, 2026-11-12); see live/README.md.
# Estimates are only used for ordering/load decisions (LL, SJF); real execution
# times are always measured, never derived from these numbers.
SECONDS_PER_UNIT: dict[str, float] = {
    "prime_count": 2.035e-06,
    "data_aggregation": 8.918e-07,
    "sha256_chain": 1.109e-06,
}


PRIME_WINDOW_START = 1_000_000


# Fixed window start keeps the cost per unit constant, so CPU time is linear in units.
def prime_count(units: int) -> dict:
    lo = PRIME_WINDOW_START
    count = 0
    for k in range(lo, lo + int(units)):
        if k % 2 == 0:
            continue
        limit = math.isqrt(k)
        for d in range(3, limit + 1, 2):
            if k % d == 0:
                break
        else:
            count += 1
    return {"primes_in_window": count, "checksum": str(count)}


DATA_CHUNK = 10_000  # records held in memory at once (bounded memory)


def data_aggregation(units: int) -> dict:
    rng = random.Random(units)
    stats: dict[int, list[float]] = {}  # key -> [n, sum, max]
    remaining = int(units)
    while remaining > 0:
        size = min(DATA_CHUNK, remaining)
        chunk = sorted((rng.randrange(16), rng.random() * 100.0) for _ in range(size))
        for key, value in chunk:
            s = stats.setdefault(key, [0, 0.0, 0.0])
            s[0] += 1
            s[1] += value
            s[2] = max(s[2], value)
        remaining -= size
    summary = {str(k): {"n": v[0], "mean": round(v[1] / v[0], 6), "max": round(v[2], 6)} for k, v in sorted(stats.items())}
    digest = hashlib.sha256(json.dumps(summary, sort_keys=True).encode()).hexdigest()[:16]
    return {"groups": len(summary), "records": int(units), "checksum": digest}


def sha256_chain(units: int) -> dict:
    block = b"cloudpulse" * 103  # ~1 KiB
    h = hashlib.sha256(block).digest()
    for _ in range(int(units)):
        h = hashlib.sha256(h + block).digest()
    return {"iterations": int(units), "checksum": h.hex()[:16]}


TASK_FUNCTIONS: dict[str, Callable[[int], dict]] = {
    "prime_count": prime_count,
    "data_aggregation": data_aggregation,
    "sha256_chain": sha256_chain,
}

MAX_UNITS = 10_000_000  # guard: keeps any single task small on a 2 GB host


def validate_task(task_type: str, units: int) -> None:
    if task_type not in TASK_FUNCTIONS:
        raise ValueError(f"Unknown task_type {task_type!r}; choose from {sorted(TASK_FUNCTIONS)}")
    if not isinstance(units, int) or isinstance(units, bool) or not 1 <= units <= MAX_UNITS:
        raise ValueError(f"units must be an integer in [1, {MAX_UNITS}]")


def run_task(task_type: str, units: int) -> dict:
    validate_task(task_type, units)
    return TASK_FUNCTIONS[task_type](units)


def estimate_seconds(task_type: str, units: int) -> float:
    return round(SECONDS_PER_UNIT[task_type] * units, 4)


# Same small/medium/large mix as the offline simulator (60/30/10 %), scaled down so a
# whole experiment fits in minutes: target reference seconds on W1.
LIVE_SIZE_RANGES: dict[str, tuple[float, float]] = {
    "small": (0.10, 0.30),
    "medium": (0.30, 1.00),
    "large": (1.00, 2.50),
}
LIVE_SIZE_MIX: dict[str, float] = {"small": 0.6, "medium": 0.3, "large": 0.1}


@dataclass(frozen=True)
class LiveTaskSpec:
    index: int
    offset: float          # seconds after the run starts at which the task is submitted
    task_type: str
    units: int
    size_class: str
    estimated_seconds: float


def generate_live_workload(
    num_tasks: int,
    seed: int,
    total_capacity: float,
    load: float = 0.85,
) -> list[LiveTaskSpec]:
    if num_tasks < 1:
        raise ValueError("num_tasks must be >= 1")
    if total_capacity <= 0 or load <= 0:
        raise ValueError("total_capacity and load must be > 0")
    rng = random.Random(seed)
    classes = list(LIVE_SIZE_MIX)
    weights = [LIVE_SIZE_MIX[c] for c in classes]
    types = sorted(TASK_FUNCTIONS)
    mean_size = sum(LIVE_SIZE_MIX[c] * sum(LIVE_SIZE_RANGES[c]) / 2 for c in classes)
    rate = load * total_capacity / mean_size
    specs, t = [], 0.0
    for i in range(num_tasks):
        size_class = rng.choices(classes, weights)[0]
        target = rng.uniform(*LIVE_SIZE_RANGES[size_class])
        task_type = rng.choice(types)
        units = max(1, int(round(target / SECONDS_PER_UNIT[task_type])))
        specs.append(
            LiveTaskSpec(i, round(t, 4), task_type, units, size_class, estimate_seconds(task_type, units))
        )
        t += rng.expovariate(rate)
    return specs


def live_workload_fingerprint(specs: list[LiveTaskSpec]) -> str:
    return hashlib.sha256(json.dumps([asdict(s) for s in specs], sort_keys=True).encode()).hexdigest()

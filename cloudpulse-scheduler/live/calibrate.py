# Run in the idle W1 container (docker compose exec worker-1 python -m live.calibrate)
# and copy the printed numbers into SECONDS_PER_UNIT in live/tasks.py.
from __future__ import annotations

import statistics
import time

from .tasks import TASK_FUNCTIONS

UNITS = {"prime_count": 300_000, "data_aggregation": 600_000, "sha256_chain": 500_000}


def main(repeats: int = 3) -> dict[str, float]:
    out = {}
    for name, units in UNITS.items():
        times = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            TASK_FUNCTIONS[name](units)
            times.append(time.perf_counter() - t0)
        out[name] = statistics.median(times) / units
        print(f"{name:18s} units={units:>8d} median={statistics.median(times):.3f}s  per_unit={out[name]:.3e}")
    return out


if __name__ == "__main__":
    main()

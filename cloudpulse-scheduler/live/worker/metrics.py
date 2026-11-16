# Process CPU is what the worker itself uses; host_* values describe the whole
# machine/VM and are labelled as such.
from __future__ import annotations

import os
from pathlib import Path

import psutil

CGROUP = Path("/sys/fs/cgroup")


def _read(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except OSError:
        return None


def cgroup_cpu_limit_cores() -> float | None:
    raw = _read(CGROUP / "cpu.max")
    if not raw:
        return None
    quota, _, period = raw.partition(" ")
    if quota == "max" or not period:
        return None
    return int(quota) / int(period)


def cgroup_memory_mb() -> tuple[float | None, float | None]:
    cur = _read(CGROUP / "memory.current")
    lim = _read(CGROUP / "memory.max")
    current = int(cur) / 2**20 if cur and cur.isdigit() else None
    limit = int(lim) / 2**20 if lim and lim.isdigit() else None
    return current, limit


class MetricsSampler:
    def __init__(self, cpu_limit_override: float | None = None) -> None:
        self.proc = psutil.Process(os.getpid())
        self.proc.cpu_percent(None)   # prime the counters; first call always returns 0
        psutil.cpu_percent(None)
        limit = cgroup_cpu_limit_cores()
        self.cpu_limit_cores = cpu_limit_override or limit or float(psutil.cpu_count() or 1)
        self.cpu_limit_source = "override" if cpu_limit_override else ("cgroup" if limit else "host_cpu_count")

    def sample(self) -> dict:
        proc_cpu = self.proc.cpu_percent(None)          # % of ONE core since previous sample
        mem_cur, mem_lim = cgroup_memory_mb()
        vm = psutil.virtual_memory()
        return {
            "process_cpu_percent": round(proc_cpu, 2),
            "cpu_limit_cores": round(self.cpu_limit_cores, 3),
            "cpu_percent_of_limit": round(min(100.0, proc_cpu / self.cpu_limit_cores), 2),
            "process_rss_mb": round(self.proc.memory_info().rss / 2**20, 2),
            "container_memory_mb": None if mem_cur is None else round(mem_cur, 2),
            "container_memory_limit_mb": None if mem_lim is None else round(mem_lim, 2),
            "host_cpu_percent": round(psutil.cpu_percent(None), 2),
            "host_memory_percent": round(vm.percent, 2),
            "num_threads": self.proc.num_threads(),
        }

from __future__ import annotations

from .base import (
    CENTRAL_QUEUE,
    CONTROL,
    PER_WORKER_QUEUE,
    PRIMARY,
    CentralQueueScheduler,
    PerWorkerQueueScheduler,
    Scheduler,
)
from .fcfs_baseline import FCFSBaselineScheduler
from .least_loaded import LeastLoadedScheduler
from .round_robin import RoundRobinScheduler
from .shortest_job_first import ShortestJobFirstScheduler
from .weighted_round_robin import WeightedRoundRobinScheduler

ALGORITHMS: dict[str, type[Scheduler]] = {
    RoundRobinScheduler.name: RoundRobinScheduler,
    WeightedRoundRobinScheduler.name: WeightedRoundRobinScheduler,
    LeastLoadedScheduler.name: LeastLoadedScheduler,
    ShortestJobFirstScheduler.name: ShortestJobFirstScheduler,
}

CONTROL_BASELINES: dict[str, type[Scheduler]] = {
    FCFSBaselineScheduler.name: FCFSBaselineScheduler,
}

ALL_CONFIGURATIONS: dict[str, type[Scheduler]] = {**ALGORITHMS, **CONTROL_BASELINES}

DISPLAY_NAMES = {
    "round_robin": "RR",
    "weighted_round_robin": "WRR",
    "least_loaded": "LL",
    "shortest_job_first": "SJF",
    "fcfs_baseline": "FCFS (control)",
}


def create_scheduler(name: str, **kwargs) -> Scheduler:
    try:
        cls = ALL_CONFIGURATIONS[name]
    except KeyError:
        raise ValueError(f"Unknown algorithm {name!r}; choose from {sorted(ALL_CONFIGURATIONS)}") from None
    return cls(**kwargs)


__all__ = [
    "ALGORITHMS",
    "ALL_CONFIGURATIONS",
    "CENTRAL_QUEUE",
    "CONTROL",
    "CONTROL_BASELINES",
    "DISPLAY_NAMES",
    "PER_WORKER_QUEUE",
    "PRIMARY",
    "CentralQueueScheduler",
    "FCFSBaselineScheduler",
    "LeastLoadedScheduler",
    "PerWorkerQueueScheduler",
    "RoundRobinScheduler",
    "Scheduler",
    "ShortestJobFirstScheduler",
    "WeightedRoundRobinScheduler",
    "create_scheduler",
]

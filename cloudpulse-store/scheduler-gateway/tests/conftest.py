import os
import sys
from pathlib import Path

# gateway/ imports `src.schedulers` from the sibling cloudpulse-scheduler application.
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cloudpulse-scheduler"))
sys.path.insert(0, str(ROOT / "cloudpulse-store" / "scheduler-gateway"))

os.environ.setdefault("QUEUE_TIMEOUT", "2")
os.environ.setdefault("HEALTH_INTERVAL", "0.2")

import pytest  # noqa: E402

from gateway.config import BackendConfig, Settings  # noqa: E402


@pytest.fixture
def settings():
    return Settings(
        algorithm="least_loaded",
        backends=[
            BackendConfig("B1", "http://b1", capacity=1.0, weight=5, slots=2),
            BackendConfig("B2", "http://b2", capacity=0.6, weight=3, slots=1),
            BackendConfig("B3", "http://b3", capacity=0.4, weight=2, slots=1),
        ],
        queue_timeout=1.0,
        health_interval=0.2,
        health_timeout=0.5,
        unhealthy_after=1,
    )

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BackendConfig:
    backend_id: str
    url: str
    capacity: float = 1.0
    weight: int = 1
    slots: int = 2          # max requests in flight on this backend at once

    @staticmethod
    def from_dict(d: dict) -> "BackendConfig":
        return BackendConfig(
            backend_id=str(d["id"]),
            url=str(d["url"]).rstrip("/"),
            capacity=float(d.get("capacity", 1.0)),
            weight=int(d.get("weight", 1)),
            slots=int(d.get("slots", 2)),
        )


DEFAULT_BACKENDS = [
    {"id": "B1", "url": "http://backend-1:8000", "capacity": 1.0, "weight": 5, "slots": 4},
    {"id": "B2", "url": "http://backend-2:8000", "capacity": 0.6, "weight": 3, "slots": 2},
    {"id": "B3", "url": "http://backend-3:8000", "capacity": 0.4, "weight": 2, "slots": 2},
]

# Initial per-route service-time estimates (seconds). They are only a starting point:
# the gateway keeps an exponentially weighted moving average of the real service time
# per route, so SJF and least-loaded improve their estimates as traffic flows.
DEFAULT_ESTIMATES: dict[str, float] = {
    "GET /api/health": 0.004,
    "GET /api/ready": 0.006,
    "GET /api/categories": 0.008,
    "GET /api/products": 0.015,
    "GET /api/products/{id}": 0.008,
    "GET /api/products/search": 0.012,
    "GET /api/orders": 0.015,
    "GET /api/orders/{id}": 0.010,
    "POST /api/orders": 0.040,
    "POST /api/contact": 0.015,
    "GET /api/stats": 0.012,
    "GET /api/metrics": 0.010,
}
FALLBACK_ESTIMATE = 0.015

_ID_SEGMENT = re.compile(r"/\d+(?=/|$)")


def route_key(method: str, path: str) -> str:
    path = path.split("?", 1)[0].rstrip("/") or "/"
    return f"{method.upper()} {_ID_SEGMENT.sub('/{id}', path)}"


@dataclass(frozen=True)
class Settings:
    algorithm: str = os.getenv("ALGORITHM", "least_loaded")
    backends: list[BackendConfig] = field(default_factory=list)
    health_interval: float = float(os.getenv("HEALTH_INTERVAL", "2"))
    health_timeout: float = float(os.getenv("HEALTH_TIMEOUT", "2"))
    unhealthy_after: int = int(os.getenv("UNHEALTHY_AFTER", "2"))          # consecutive failed probes
    queue_timeout: float = float(os.getenv("QUEUE_TIMEOUT", "10"))         # seconds a request may wait
    upstream_timeout: float = float(os.getenv("UPSTREAM_TIMEOUT", "30"))
    max_attempts: int = int(os.getenv("MAX_ATTEMPTS", "3"))
    ewma_alpha: float = float(os.getenv("EWMA_ALPHA", "0.2"))
    recent_limit: int = int(os.getenv("RECENT_LIMIT", "60"))
    service_name: str = os.getenv("SERVICE_NAME", "cloudpulse-scheduler-gateway")
    app_version: str = os.getenv("APP_VERSION", "1.0.0")


def load_settings() -> Settings:
    raw = os.getenv("BACKENDS_JSON", "").strip()
    items = json.loads(raw) if raw else DEFAULT_BACKENDS
    backends = [BackendConfig.from_dict(d) for d in items]
    if not backends:
        raise ValueError("BACKENDS_JSON must list at least one backend")
    ids = [b.backend_id for b in backends]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate backend ids in BACKENDS_JSON: {ids}")
    return Settings(backends=backends)

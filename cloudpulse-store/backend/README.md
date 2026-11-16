# CloudPulse Store — Backend

FastAPI REST API for CloudPulse Store. It serves the product catalogue, accepts demonstration
orders and contact messages, stores everything in SQLite, and exposes health checks and
Prometheus metrics that the monitoring stack scrapes.

In Docker the backend runs as **three replicas** (`backend-1/2/3`, CPU quotas 0.75 / 0.45 / 0.30,
same image) behind the scheduling gateway; it is reachable only through Nginx (`/api/*`) → gateway,
and port 8000 is never published. All replicas share one SQLite database (WAL mode); only
replica 1 creates tables and seeds.

## Contents

| Path | Responsibility |
|---|---|
| [`app/`](app/README.md) | Application package: routers, configuration, metrics, database, schemas, services |
| [`tests/`](tests/README.md) | Pytest suite (38 tests) using a temporary SQLite database |
| `requirements.txt` | Pinned runtime dependencies (FastAPI, Uvicorn, SQLAlchemy, Pydantic, email-validator, prometheus-client) |
| `requirements-dev.txt` | Runtime dependencies + pytest and HTTPX |
| `pytest.ini` | Pytest settings (`testpaths = tests`, quiet output) |
| `Dockerfile` | `python:3.11-slim` image, non-root user, health check on `/api/health`, one Uvicorn worker |
| `.dockerignore` | Keeps tests, virtual environments and local databases out of the image |

## Run locally without Docker

```bash
cd cloudpulse-store/backend
python3.11 -m venv .venv            # or: uv venv --python 3.11 .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000    # http://localhost:8000/api/docs
pytest -v                                     # 38 tests
```

Windows (PowerShell; translation table in the [root README](../../README.md#windows-powershell)):

```powershell
cd cloudpulse-store\backend
py -3.11 -m venv .venv                        # or: uv venv --python 3.11 .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000   # http://localhost:8000/api/docs
.venv\Scripts\python -m pytest -v             # 38 tests
```

Without Docker the database file is created at `backend/data/cloudpulse.db` (ignored by Git).

## Configuration

All settings come from environment variables (see `app/core/config.py`): `DATABASE_URL`,
`ENVIRONMENT`, `LOG_LEVEL`, `APP_VERSION`, `SERVICE_NAME`, `SEED_ON_STARTUP`, `ENABLE_CHAOS`
(failure demo `POST /admin/crash`, off by default, enabled in `compose.yaml`), `CORS_ORIGINS`. In
Docker they are set by `../compose.yaml` from `../.env`. No secrets are stored in code.

## Related documentation
- [API reference](../docs/API_DOCUMENTATION.md)
- [Architecture](../docs/ARCHITECTURE.md)
- [Testing guide](../docs/TESTING_GUIDE.md)

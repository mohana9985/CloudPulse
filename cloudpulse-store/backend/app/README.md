# `app/` — Backend application package

The importable Python package that Uvicorn runs as `app.main:app`.

| Path | Responsibility |
|---|---|
| `main.py` | Creates the FastAPI app (docs at `/api/docs`, `/api/redoc`), runs the lifespan hook (create tables, seed products), adds CORS and Prometheus middleware, registers all routers |
| [`api/`](api/README.md) | HTTP routers: health, products, orders, contact, monitoring |
| [`core/`](core/README.md) | Settings from environment variables and Prometheus instrumentation |
| [`database/`](database/README.md) | SQLAlchemy engine/session, ORM models, seed data |
| [`schemas/`](schemas/README.md) | Pydantic request/response models |
| [`services/`](services/README.md) | Business logic used by the routers |

Request flow: **router (`api/`) → validation (`schemas/`) → logic (`services/`) → ORM (`database/`)**,
with `core/metrics.py` recording every request on the way in and out.

See also: [backend README](../README.md), [architecture](../../docs/ARCHITECTURE.md).

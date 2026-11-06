# `backend/tests/` — Backend test suite

Pytest suite for the FastAPI backend: **33 tests**.

| File | Tests | Covers |
|---|---|---|
| `conftest.py` | — | Points `DATABASE_URL` at a fresh temporary SQLite file before the app is imported; session-wide `TestClient`; `valid_order` fixture |
| `test_health.py` | 3 | `/api/health`, `/api/ready` (database check), OpenAPI docs available |
| `test_products.py` | 13 | Listing, category filter, sorting, pagination, invalid sort, details, 404/422 cases, categories, case-insensitive search |
| `test_orders.py` | 11 | Order creation and retrieval, unknown product (404), insufficient stock (409 + rollback), validation, shipping fee, UTC timestamps, contact form submission/validation |
| `test_monitoring.py` | 6 | Prometheus format, route-template labels, `unmatched` grouping, error counting, `/api/stats`, no configuration leakage |

Tests never touch the real database file.

```bash
cd cloudpulse-store/backend
source .venv/bin/activate          # created as shown in ../README.md
pytest -v
```

System-level checks (browser flow, persistence, Docker) are in
[`docs/TESTING_GUIDE.md`](../../docs/TESTING_GUIDE.md).

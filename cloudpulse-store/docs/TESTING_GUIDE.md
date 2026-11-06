# Testing Guide

Three levels of testing:

1. **Automated backend tests** (pytest + HTTPX TestClient) — fast, no Docker needed.
2. **System verification** of the running Docker stack (curl + browser checklist).
3. **Load tests** with Locust — see [`../load-testing/README.md`](../load-testing/README.md).

Only record a check as passed after you have actually run it.

## 1. Backend unit and integration tests

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate     # first time only
pip install -r requirements-dev.txt                        # first time only
pytest -v
```

Each run uses a fresh temporary SQLite database (see `tests/conftest.py`), so tests never
touch real data. The tests call the real FastAPI app in-process, including startup
(table creation + seeding) and the Prometheus middleware.

| File | Covers |
|---|---|
| `test_health.py` | `/api/health`, `/api/ready`, Swagger docs available |
| `test_products.py` | Listing, category filter, price sorting, pagination, invalid sort, details, 404/422, categories, search (case-insensitive, empty result, missing query) |
| `test_orders.py` | Create order, get by ID, recent orders, unknown product (404), insufficient stock (409 **and rollback of stock**), validation errors (422), shipping fee rule, UTC timestamps, contact form submission + validation |
| `test_monitoring.py` | Prometheus format and metric names, route templates instead of raw IDs, unknown URLs grouped as `unmatched`, error counter, `/api/stats`, no configuration leaked |

## 2. Frontend build

```bash
cd frontend
npm ci
npm run build          # must finish with "built in ..." and no errors
```

## 3. System verification (Docker)

Start the stack:

```bash
docker compose up --build -d
docker compose ps                      # backend and frontend: "(healthy)"
```

### 3.1 Endpoints

```bash
curl -i http://localhost/api/health                     # 200, "status":"ok"
curl -i http://localhost/api/ready                      # 200, "database":"ok"
curl -s http://localhost/api/products | head -c 300     # JSON with "items"
curl -s http://localhost/api/products/1                 # one product
curl -s "http://localhost/api/products/search?q=book"   # array of books
curl -s http://localhost/api/categories                 # 6 categories
curl -s -o /dev/null -w "%{http_code}\n" http://localhost/api/products/99999   # 404
curl -s -o /dev/null -w "%{http_code}\n" http://localhost/api/docs             # 200
curl -s http://localhost/api/metrics | grep cloudpulse_http_requests_total | head
curl -s http://localhost/api/stats
```

Create an order and read it back:

```bash
curl -s -X POST http://localhost/api/orders -H "Content-Type: application/json" \
  -d '{"customer_name":"Test User","email":"test@example.com","address":"1 Test Road, Pilani","items":[{"product_id":1,"quantity":1}]}'
curl -s http://localhost/api/orders
```

Security checks (all must fail to return data):

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/health   # connection refused (backend not published)
curl -s -o /dev/null -w "%{http_code}\n" http://localhost/cloudpulse.db     # 403 or SPA page, never the database
curl -s -o /dev/null -w "%{http_code}\n" http://localhost/.env              # 403
```

### 3.2 Frontend-to-backend (browser)

Open <http://localhost> and check:

- [ ] Home page shows featured products and categories (data comes from `/api`).
- [ ] Search from the home page opens the Products page with results.
- [ ] Products page: category filter, price sorting, pagination work.
- [ ] Product details page shows price, category, availability; *Add to cart* updates the cart badge.
- [ ] Cart: change quantity, remove item, subtotal/total update; empty cart message appears.
- [ ] Reload the page — the cart is still there (localStorage).
- [ ] Checkout: submitting empty fields shows validation errors; a valid order opens the confirmation page with an order ID.
- [ ] Contact: invalid form shows errors; a valid message shows a confirmation.
- [ ] Unknown URL (e.g. `/does-not-exist`) shows the Not Found page.
- [ ] Browser DevTools -> Console: no errors. Network tab: all calls go to `/api/...` on the same origin (no CORS errors).
- [ ] Narrow the window to phone width: navigation collapses into the menu button.

### 3.3 Database persistence after restart

```bash
curl -s http://localhost/api/stats | grep -o '"total_orders":[0-9]*'     # note the number, e.g. 3
docker compose restart backend
docker compose down && docker compose up -d                              # recreate containers
curl -s http://localhost/api/stats | grep -o '"total_orders":[0-9]*'     # same number -> data persisted
```

`docker compose down -v` removes the volume, after which the count returns to 0 (expected).

### 3.4 Optional monitoring profile

```bash
docker compose --profile monitoring up -d
```

- Prometheus <http://localhost:9090/targets>: `cloudpulse-store-backend` is **UP**.
- Grafana <http://localhost:3000>: dashboard *CloudPulse Store - Application Overview* shows data
  (generate traffic with Locust first).

## 4. Load tests

```bash
cd load-testing
source .venv/bin/activate
./run_scenarios.sh http://localhost 10 5 30s     # quick check that all scenarios run
```

Expected: four reports in `load-testing/results/<timestamp>/` and a summary table.
Use the test plan in the load-testing README for the real measurements.

## Verification log template

| # | Check | Command / action | Result | Date |
|---|---|---|---|---|
| 1 | Backend dependencies install | `pip install -r requirements-dev.txt` | | |
| 2 | Frontend build | `npm run build` | | |
| 3 | Backend tests | `pytest -v` | | |
| 4 | All API endpoints | section 3.1 | | |
| 5 | Frontend-to-backend | section 3.2 | | |
| 6 | Persistence after restart | section 3.3 | | |
| 7 | Compose starts all services | `docker compose ps` | | |
| 8 | Website at localhost | browser | | |
| 9 | Health endpoints | `/api/health`, `/api/ready` | | |
| 10 | Prometheus metrics | `/api/metrics` | | |
| 11 | Locust scripts run | `run_scenarios.sh` | | |

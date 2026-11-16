# `app/api/` — HTTP routers

One FastAPI `APIRouter` per area, mounted under the `/api` prefix (except the failure-demo router `/admin`) and registered in
`app/main.py`. Routers stay thin: they validate input with [`schemas`](../schemas/README.md) and
call [`services`](../services/README.md).

| File | Endpoints |
|---|---|
| `health.py` | `GET /api/health` (liveness), `GET /api/ready` (database readiness, 503 if not ready) |
| `products.py` | `GET /api/products` (filter, search, sort, paginate), `GET /api/products/search`, `GET /api/products/{product_id}`, `GET /api/categories` |
| `orders.py` | `POST /api/orders` (demonstration order, no payment), `GET /api/orders`, `GET /api/orders/{order_id}` |
| `contact.py` | `POST /api/contact` |
| `monitoring.py` | `GET /api/metrics` (Prometheus text format), `GET /api/stats` (JSON totals and uptime, no secrets) |
| `chaos.py` | `POST /admin/crash?down_seconds=N` — failure demo (dashboard "Real crash"): exits the process and keeps the port closed for N s, then Docker restarts it. Off unless `ENABLE_CHAOS=true`; outside `/api/`, so Nginx never forwards it; refuses proxied requests. Only the scheduling gateway calls it, over the private Docker network |

Full request/response examples: [`docs/API_DOCUMENTATION.md`](../../../docs/API_DOCUMENTATION.md).

# `app/api/` — HTTP routers

One FastAPI `APIRouter` per area, all mounted under the `/api` prefix and registered in
`app/main.py`. Routers stay thin: they validate input with [`schemas`](../schemas/README.md) and
call [`services`](../services/README.md).

| File | Endpoints |
|---|---|
| `health.py` | `GET /api/health` (liveness), `GET /api/ready` (database readiness, 503 if not ready) |
| `products.py` | `GET /api/products` (filter, search, sort, paginate), `GET /api/products/search`, `GET /api/products/{product_id}`, `GET /api/categories` |
| `orders.py` | `POST /api/orders` (demonstration order, no payment), `GET /api/orders`, `GET /api/orders/{order_id}` |
| `contact.py` | `POST /api/contact` |
| `monitoring.py` | `GET /api/metrics` (Prometheus text format), `GET /api/stats` (JSON totals and uptime, no secrets) |

Full request/response examples: [`docs/API_DOCUMENTATION.md`](../../../docs/API_DOCUMENTATION.md).

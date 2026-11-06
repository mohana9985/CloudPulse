# Architecture

CloudPulse Store is a small three-tier web application packaged as Docker containers.

```
                 Browser / Locust / CloudPulse Monitoring Dashboard
                                   |
                                   | HTTP :80  (only public port)
                                   v
   +---------------------------- frontend container ----------------------------+
   |  Nginx 1.27                                                                 |
   |   /              -> React single-page app (static files from Vite build)   |
   |   /products/*.svg-> local product images                                    |
   |   /api/*         -> proxy to backend:8000                                   |
   |   /nginx-health  -> Nginx liveness probe                                    |
   +-------------------------------------|---------------------------------------+
                                         | internal Docker network "cloudpulse"
                                         v
   +---------------------------- backend container -----------------------------+
   |  Uvicorn + FastAPI (Python 3.11)                                            |
   |   PrometheusMiddleware -> counts, durations, errors, in-flight requests     |
   |   Routers: health, products, orders, contact, monitoring                    |
   |   Services: business logic (search, stock checks, order transactions)       |
   |   SQLAlchemy ORM                                                            |
   +-------------------------------------|---------------------------------------+
                                         v
                       SQLite file /app/data/cloudpulse.db
                       (Docker named volume "sqlite_data")

   Optional profile "monitoring":
     Prometheus  --scrapes backend:8000/api/metrics every 15 s-->  Grafana dashboard
     (both bound to 127.0.0.1 only)
```

## Why this design

| Decision | Reason |
|---|---|
| Nginx serves the React build **and** proxies `/api` | Browser sees one origin, so there are no CORS problems; only one port is public |
| Backend not published on the host | Smaller attack surface; all access goes through Nginx (which is also what we monitor) |
| SQLite + named volume | Zero setup, survives container restarts/rebuilds; `DATABASE_URL` makes PostgreSQL a config change |
| One Uvicorn worker | Prometheus counters live in one process, so metrics are exact without multiprocess mode |
| Route templates as metric labels | `/api/products/{product_id}` instead of `/api/products/17` keeps Prometheus cardinality low |
| Cart in `localStorage` | No login/session needed; the server only sees the final order (like many real shops) |
| Multi-stage frontend image | Node is only used to build; the final image is a ~50 MB Nginx image |

## Backend layers

```
app/
  main.py            FastAPI app, middleware, router registration, startup (create tables + seed)
  api/               HTTP layer: validates input (Pydantic), maps errors to status codes
  services/          Business rules: filtering, search, stock checks, order transaction
  schemas/           Pydantic request/response models (input validation lives here)
  database/          Engine/session (connection.py), ORM tables (models.py), seed data (seed.py)
  core/              Settings from environment variables (config.py), Prometheus metrics (metrics.py)
```

A request flows `router -> service -> SQLAlchemy -> SQLite`, and the middleware
wraps the whole thing to record metrics.

### Order creation (transaction)

1. Load all requested products; unknown ID -> **404**, whole order rejected.
2. For each item run `UPDATE products SET stock = stock - qty WHERE id = ? AND stock >= qty`.
   If no row is updated -> **409 Insufficient stock**. The conditional update is atomic,
   so two simultaneous orders can never oversell.
3. Insert the order and its items, compute subtotal + shipping (free from INR 999, else INR 99).
4. `COMMIT`. Any error -> `ROLLBACK`, so stock is never decremented for a failed order.

SQLite runs in WAL mode, so product reads continue while an order is being written.

## Frontend structure

```
src/
  main.jsx               Router + CartProvider
  App.jsx                Layout (Navbar, Footer) and routes
  pages/                 Home, Products, ProductDetails, Cart, Checkout,
                         OrderConfirmation, About, Contact, NotFound
  components/            Navbar, Footer, ProductCard, ProductGrid, ProductImage,
                         SearchBar, LoadingSpinner, ErrorMessage
  context/CartContext    Cart state + localStorage persistence
  services/api.js        All Axios calls (base URL /api) + error-message helper
  hooks/useFetch.js      loading / error / data state for API calls
  utils/                 Price formatting, shipping rule, form validation
```

## Database schema

```
products                      orders                       order_items
---------------------         -------------------          ---------------------
id            PK              id             PK            id          PK
name                          customer_name                order_id    FK -> orders.id
description                   email                        product_id  FK -> products.id
price         >= 0            address                      quantity    > 0
category      (indexed)       total_amount                 unit_price  (price at order time)
image_path                    status  (CONFIRMED)
stock_quantity >= 0           created_at (indexed)
created_at

contact_messages
---------------------
id, name, email, subject, message, created_at
```

`unit_price` is copied into `order_items` so old orders keep their original price
even if a product price changes later. All timestamps are stored in UTC.

## Monitoring surface

| URL | Used by | Content |
|---|---|---|
| `/nginx-health` | Docker, uptime checks | Nginx alive (no backend call) |
| `/api/health` | Docker, CloudPulse dashboard | Backend process alive |
| `/api/ready` | Docker health check | Backend + database usable (503 otherwise) |
| `/api/metrics` | Prometheus | Prometheus text format |
| `/api/stats` | CloudPulse dashboard, humans | JSON totals + uptime |

Metric names: `cloudpulse_http_requests_total`, `cloudpulse_http_request_duration_seconds`,
`cloudpulse_http_errors_total`, `cloudpulse_http_requests_in_progress`,
`cloudpulse_app_uptime_seconds`, `cloudpulse_app_start_time_seconds`,
`cloudpulse_orders_created_total`, `cloudpulse_contact_messages_total`, `cloudpulse_app_info`,
plus the default `process_*` (CPU, memory, file descriptors) and `python_*` metrics.

Host-level metrics (EC2 CPU, RAM, disk, network) are **not** part of this website;
the separate CloudPulse Monitoring Dashboard collects them (e.g. via CloudWatch or an agent).

## Scope boundaries

Not implemented on purpose: real payments, user accounts/authentication, the
CloudPulse monitoring dashboard itself, scheduling algorithms, AI/ML features.

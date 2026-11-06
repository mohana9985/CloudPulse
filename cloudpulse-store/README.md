# CloudPulse Store

A lightweight, Docker-based **demonstration e-commerce website** built as the first
component of the university Cloud Computing project
**CloudPulse: Intelligent Cloud Resource Monitoring and Workload Scheduling System**.

> Part of the [CloudPulse monorepo](../README.md); the scheduling simulator is in
> [`../cloudpulse-scheduler/`](../cloudpulse-scheduler/README.md).

The store looks and behaves like a small online shop (browse, search, cart, checkout,
contact form), but no real products are sold and no payments are taken. Its purpose is
to generate realistic web and API traffic that the separate **CloudPulse Monitoring
Dashboard** observes: availability, response times, API performance, traffic, errors
and server resource usage.

```bash
docker compose up --build -d     # start  -> http://localhost
docker compose down              # stop
```

---

## Contents

1. [Objectives](#objectives)
2. [Technology stack](#technology-stack)
3. [Architecture](#architecture)
4. [Folder structure](#folder-structure)
5. [Prerequisites](#prerequisites)
6. [Local installation](#local-installation)
7. [Docker commands](#docker-commands)
8. [Website URLs](#website-urls)
9. [API endpoint summary](#api-endpoint-summary)
10. [Database](#database)
11. [Monitoring](#monitoring)
12. [Load testing](#load-testing)
13. [AWS deployment](#aws-deployment)
14. [Testing](#testing)
15. [Troubleshooting](#troubleshooting)
16. [Limitations](#limitations)
17. [Future improvements](#future-improvements)

## Objectives

1. Run on a local MacBook (Apple Silicon, 8 GB RAM).
2. Use a proper frontend / backend architecture (React SPA + FastAPI REST API).
3. Provide realistic user interactions and API endpoints.
4. Run with Docker and Docker Compose; deploy to AWS EC2 Ubuntu.
5. Accept external HTTP requests for monitoring.
6. Expose health checks and Prometheus performance metrics.
7. Support automated load testing with Locust across different traffic patterns.
8. Stay simple enough for a two-person university project to explain fully.

## Technology stack

| Layer | Technologies |
|---|---|
| Frontend | React 18, Vite, JavaScript, Tailwind CSS, React Router, Axios |
| Backend | Python 3.11, FastAPI, Pydantic, SQLAlchemy 2, Uvicorn |
| Database | SQLite (Docker named volume); swappable via `DATABASE_URL` |
| Infrastructure | Docker, Docker Compose, Nginx, AWS EC2 Ubuntu |
| Testing / monitoring | Pytest, HTTPX, Locust, Prometheus Python client, optional Prometheus + Grafana |

## Architecture

```
Browser / Locust / CloudPulse Dashboard
            │  HTTP :80 (only public port)
            ▼
┌──────── frontend container: Nginx ────────┐
│  /        → React build (static files)    │
│  /api/*   → proxy to backend:8000         │
└───────────────────┬───────────────────────┘
                    │ internal Docker network
                    ▼
┌──────── backend container: FastAPI ───────┐
│  Prometheus middleware → /api/metrics     │
│  routers → services → SQLAlchemy          │
└───────────────────┬───────────────────────┘
                    ▼
        SQLite on volume "sqlite_data"

Optional profile "monitoring": Prometheus (scrapes /api/metrics) → Grafana
```

Because Nginx serves both the website and the API from the same origin, the browser
never makes cross-origin requests — **no CORS configuration is needed**. The backend
port is never published. Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Folder structure

```
cloudpulse-store/
├── frontend/                  React + Vite app, built and served by Nginx
│   ├── public/products/       24 local SVG product images (no external image services)
│   ├── src/
│   │   ├── components/        Navbar, Footer, ProductCard, ProductGrid, SearchBar, ...
│   │   ├── pages/             Home, Products, ProductDetails, Cart, Checkout,
│   │   │                      OrderConfirmation, About, Contact, NotFound
│   │   ├── context/           CartContext (cart state + localStorage)
│   │   ├── services/api.js    All API calls (Axios, base URL /api)
│   │   ├── hooks/, utils/     useFetch, formatting, validation
│   │   └── App.jsx, main.jsx, index.css
│   ├── Dockerfile             Multi-stage: Node build → Nginx
│   └── nginx.conf             SPA routing + /api reverse proxy
├── backend/                   FastAPI service
│   ├── app/
│   │   ├── api/               health, products, orders, contact, monitoring routers
│   │   ├── core/              config (env vars), metrics (Prometheus)
│   │   ├── database/          connection, models, seed (24 products)
│   │   ├── schemas/           Pydantic request/response models
│   │   ├── services/          product, order, contact business logic
│   │   └── main.py
│   ├── tests/                 pytest suite (33 tests)
│   ├── requirements.txt       Runtime dependencies
│   ├── requirements-dev.txt   + pytest, httpx
│   └── Dockerfile
├── monitoring/                Prometheus scrape config, Grafana datasource + dashboard
├── load-testing/              Locust scenarios, runner script, results summariser
├── deployment/                EC2 setup/deploy scripts, host Nginx config for HTTPS
├── docs/                      Architecture, API, local setup, AWS, testing guides
├── compose.yaml
├── .env.example
├── .gitignore
└── README.md
```

## Prerequisites

* **Docker Desktop** for Mac (Apple Silicon) — or OrbStack / Colima. Give it ~3-4 GB RAM.
* Optional for development/testing: Python 3.11, Node.js 20.19+ (22 recommended), Git.

## Local installation

```bash
cd cloudpulse-store
cp .env.example .env            # optional, defaults work
docker compose up --build -d
docker compose ps               # wait until backend and frontend are "healthy"
open http://localhost
```

Development without Docker (hot reload), tests and Colima setup:
see [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md).

## Docker commands

| Task | Command |
|---|---|
| Build and start | `docker compose up --build -d` |
| Stop (keep data) | `docker compose down` |
| Stop and **delete database** | `docker compose down -v` |
| Status / health | `docker compose ps` |
| Logs | `docker compose logs -f` / `docker compose logs -f backend` |
| Restart backend | `docker compose restart backend` |
| Container CPU/RAM | `docker stats` |
| Start with Prometheus + Grafana | `docker compose --profile monitoring up --build -d` |
| Stop including monitoring | `docker compose --profile monitoring down` |

## Website URLs

| URL | Purpose |
|---|---|
| <http://localhost> | Website |
| <http://localhost/api/docs> | API documentation (Swagger UI) |
| <http://localhost/api/redoc> | API documentation (ReDoc) |
| <http://localhost/api/health> | Health check |
| <http://localhost/api/ready> | Readiness check (database) |
| <http://localhost/api/metrics> | Prometheus metrics |
| <http://localhost/api/stats> | JSON statistics |
| <http://localhost/nginx-health> | Nginx liveness |
| <http://localhost:9090> | Prometheus (monitoring profile only) |
| <http://localhost:3000> | Grafana (monitoring profile only) |

## API endpoint summary

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Status, service name, timestamp |
| GET | `/api/ready` | App + database readiness (503 if not ready) |
| GET | `/api/products` | All products; optional `category`, `q`, `sort`, `page`, `page_size` |
| GET | `/api/products/{product_id}` | Product details (404 if unknown) |
| GET | `/api/products/search?q=` | Case-insensitive search |
| GET | `/api/categories` | Categories with product counts |
| POST | `/api/orders` | Create demonstration order (stock checked, transactional) |
| GET | `/api/orders/{order_id}` | Order details |
| GET | `/api/orders` | Recent orders |
| POST | `/api/contact` | Validate and store contact message |
| GET | `/api/metrics` | Prometheus metrics |
| GET | `/api/stats` | Request/product/order/contact totals and uptime |

Full request/response examples: [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md).

## Database

SQLite file `/app/data/cloudpulse.db` inside the backend container, stored on the
Docker named volume `sqlite_data`, so it survives restarts and rebuilds.

| Table | Columns |
|---|---|
| `products` | id, name, description, price, category, image_path, stock_quantity, created_at |
| `orders` | id, customer_name, email, address, total_amount, status, created_at |
| `order_items` | id, order_id → orders, product_id → products, quantity, unit_price |
| `contact_messages` | id, name, email, subject, message, created_at |

* Tables are created automatically at startup.
* **24 demo products** in 6 categories are seeded only if the table is empty (no duplicates on restart).
* Orders run in one transaction with an atomic stock check (`409` on insufficient stock,
  `404` on unknown product, full rollback on any error).
* Switch to PostgreSQL later by changing `DATABASE_URL` and adding a driver — no code changes.
* Reset everything: `docker compose down -v && docker compose up -d`.

## Monitoring

The backend records, for every request, using route templates as labels
(e.g. `/api/products/{product_id}`) to keep cardinality low:

| Metric | Meaning |
|---|---|
| `cloudpulse_http_requests_total` | Request count by method, endpoint, status |
| `cloudpulse_http_request_duration_seconds` | Latency histogram by method, endpoint |
| `cloudpulse_http_errors_total` | Responses with status ≥ 400 |
| `cloudpulse_http_requests_in_progress` | Active requests |
| `cloudpulse_app_uptime_seconds` | Process uptime |
| `cloudpulse_orders_created_total`, `cloudpulse_contact_messages_total` | Business events |
| `process_*` | Backend CPU time, memory, open files (from prometheus_client) |

The CloudPulse Monitoring Dashboard can poll `/api/health`, `/api/ready`, `/api/stats`
and scrape `/api/metrics`. The optional `monitoring` profile starts Prometheus and a
pre-provisioned Grafana dashboard (requests/s, error rate, p50/p95/p99 latency,
in-flight requests, orders per minute). No endpoint exposes secrets or configuration.

On a public server you may restrict `/api/metrics` to your monitoring server's IP —
see the commented example in `frontend/nginx.conf`.

## Load testing

Four Locust scenarios in [`load-testing/`](load-testing/README.md):
`BrowsingUser`, `SearchUser`, `OrderUser`, `MixedWorkloadUser`.

```bash
cd load-testing
python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
locust -f locustfile.py --host http://localhost             # web UI at http://localhost:8089
./run_scenarios.sh http://localhost 20 5 1m                 # all scenarios headless + summary table
```

Results (RPS, average, median, p95, failure %, total requests) are read from Locust's
own CSV output. Record only numbers from your own runs.

## AWS deployment

```bash
ssh -i ~/.ssh/cloudpulse-key.pem ubuntu@<EC2-public-IP>
git clone <repo-url> cloudpulse && cd cloudpulse/cloudpulse-store   # monorepo: store is a subfolder
bash deployment/aws/ec2-setup.sh       # installs Docker; then log out and back in
bash deployment/aws/deploy.sh          # build, start, health check, print URLs
```

In the monorepo, `deploy.sh` skips its own `git pull` (the `.git` folder is one level up), so
update with `git -C .. pull --ff-only` before re-running it.

Security group: SSH 22 from **your IP only**, HTTP 80 (and HTTPS 443) from anywhere.
Backend, Prometheus and Grafana ports are never public. Full guide, HTTPS with Let's
Encrypt, and cost advice: [docs/AWS_DEPLOYMENT.md](docs/AWS_DEPLOYMENT.md).

> **Cost warning:** a running EC2 instance, its EBS disk and any Elastic IP are billed.
> Stop the instance when not in use and terminate it when the project is finished.
> Free Tier eligibility is not assumed.

## Testing

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -v                               # 33 tests, temporary database
cd ../frontend && npm ci && npm run build
```

System checks (endpoints, browser flow, persistence after restart, metrics):
[docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md).

## Troubleshooting

| Problem | Solution |
|---|---|
| `Cannot connect to the Docker daemon` | Start Docker Desktop (or `colima start`) |
| `port is already allocated` / port 80 busy | Set `HTTP_PORT=8080` in `.env`, open <http://localhost:8080> |
| Website loads but shows "Cannot reach the server" | Backend unhealthy: `docker compose ps`, `docker compose logs backend` |
| `502 Bad Gateway` right after start | Backend still starting; wait for `(healthy)` |
| Changes not visible | Rebuild: `docker compose up --build -d`; hard-refresh the browser |
| Products show "Out of stock" after many load tests | Expected; reset with `docker compose down -v && docker compose up -d` |
| Slow first build on 8 GB Mac | Close other apps; give Docker 3-4 GB RAM; later builds use the cache |
| `npm run dev` API errors | Backend must run on port 8000 (`uvicorn app.main:app --reload --port 8000`) |

## Limitations

* Demonstration only: no payments, user accounts, authentication or admin interface.
* SQLite allows one writer at a time; heavy concurrent ordering queues writes (fine for this project, a limit worth measuring).
* One Uvicorn worker per container (keeps metrics exact; limits CPU parallelism).
* `total_api_requests` in `/api/stats` resets when the backend restarts (database totals do not).
* Product images are simple local SVG placeholders.
* HTTPS requires your own domain.

## Future improvements

* PostgreSQL (e.g. Amazon RDS) for concurrent writes; Prometheus multiprocess mode with several workers.
* Horizontal scaling behind an Application Load Balancer / Auto Scaling group for scheduling experiments.
* CI pipeline (GitHub Actions) running tests and building images; images pushed to Amazon ECR.
* Structured JSON logs and log shipping (CloudWatch Logs).
* Simple admin page to restock products between load tests.

## License

MIT — see the repository [LICENSE](../LICENSE).

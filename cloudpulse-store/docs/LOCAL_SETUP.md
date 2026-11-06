# Local Setup (macOS, Apple Silicon)

Tested on a MacBook with an M1 chip and 8 GB RAM. All images used are multi-architecture,
so they run natively on Apple Silicon (arm64) and on x86/ARM EC2 instances.

## 1. Prerequisites

| Tool | Needed for | Install |
|---|---|---|
| Docker Desktop (or OrbStack / Colima) | Running the full stack | <https://www.docker.com/products/docker-desktop/> (choose "Apple Silicon") |
| Git | Cloning / version control | `xcode-select --install` |
| Python 3.11 | Backend tests, Locust (optional without Docker) | `brew install python@3.11` or `uv python install 3.11` |
| Node.js 20.19+ / 22 | Frontend dev server (optional) | `brew install node` |

Only Docker is required to *run* the website. Python and Node are for development and testing.

**Docker Desktop on 8 GB RAM:** Settings -> Resources -> set Memory to about 3-4 GB.
The stack itself uses well under 1 GB (backend limited to 512 MB, Nginx to 128 MB).

Lightweight alternative to Docker Desktop:

```bash
brew install colima docker docker-compose
colima start --cpu 2 --memory 3
# let the docker CLI find the compose plugin (as Homebrew instructs), in ~/.docker/config.json:
#   { "cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"] }
docker compose version
# after a reboot: colima start      to stop the VM: colima stop
```

## 2. Run with Docker (recommended)

```bash
cd cloudpulse-store
cp .env.example .env          # optional; defaults work without it
docker compose up --build -d  # first build takes a few minutes
docker compose ps             # both services should show "healthy"
```

| URL | What |
|---|---|
| <http://localhost> | Website |
| <http://localhost/api/docs> | API documentation (Swagger UI) |
| <http://localhost/api/health> | Health check |
| <http://localhost/api/ready> | Readiness check (includes database) |
| <http://localhost/api/metrics> | Prometheus metrics |
| <http://localhost/api/stats> | JSON statistics |

Stop:

```bash
docker compose down           # keeps the database volume
docker compose down -v        # ALSO deletes the database (orders, contact messages, stock levels)
```

### Optional: Prometheus + Grafana

```bash
docker compose --profile monitoring up --build -d
```

* Prometheus: <http://localhost:9090> (Status -> Targets shows `cloudpulse-store-backend` UP)
* Grafana: <http://localhost:3000> - login with `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD`
  from `.env` (defaults `admin` / `change-me-in-env` if no `.env`). The dashboard
  *CloudPulse -> CloudPulse Store - Application Overview* is provisioned automatically.

Stop including monitoring: `docker compose --profile monitoring down`.

### Port 80 already in use?

Set a different port in `.env`, e.g. `HTTP_PORT=8080`, then `docker compose up -d`
and open <http://localhost:8080>.

## 3. Useful Docker commands

```bash
docker compose logs -f                 # follow all logs
docker compose logs -f backend         # backend only
docker compose ps                      # status + health
docker compose restart backend         # restart one service
docker compose up --build -d           # rebuild after code changes
docker compose exec backend sh         # shell inside the backend container
docker stats                           # live CPU / memory of each container
docker volume ls                       # see cloudpulse-store_sqlite_data
```

Inspect the database:

```bash
docker compose exec backend python -c "import sqlite3; c=sqlite3.connect('/app/data/cloudpulse.db'); print(c.execute('select count(*) from orders').fetchone())"
```

## 4. Development mode without Docker (hot reload)

### Backend

```bash
cd backend
python3.11 -m venv .venv               # or: uv venv --python 3.11 .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

The database is created at `backend/data/cloudpulse.db` (ignored by git).
API docs: <http://localhost:8000/api/docs>.

### Frontend (second terminal)

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Vite proxies `/api` to `http://localhost:8000`, so the
browser still sees one origin (no CORS issues), exactly like Nginx does in Docker.

Production build check: `npm run build` (output in `frontend/dist/`).

## 5. Tests

```bash
cd backend && source .venv/bin/activate && pytest -v
```

See [TESTING_GUIDE.md](TESTING_GUIDE.md) for the full verification checklist and load tests.

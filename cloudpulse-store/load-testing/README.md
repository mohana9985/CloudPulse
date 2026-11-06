# Load Testing with Locust

Locust simulates many visitors using CloudPulse Store at the same time so the
CloudPulse Monitoring Dashboard (and Prometheus) have realistic traffic to observe.

All traffic is sent to the **public entry point** (Nginx on port 80), so every
request passes through Nginx -> FastAPI -> SQLite, exactly like a real visitor.

## Files

| File | Purpose |
|---|---|
| `locustfile.py` | The four user scenarios |
| `run_scenarios.sh` | Runs all four scenarios headless, one after another, and saves reports |
| `summarize_results.py` | Prints the key numbers from Locust CSV files as a Markdown table |
| `requirements.txt` | Pinned Locust version |

## Scenarios

| Class | Scenario | What a user does |
|---|---|---|
| `BrowsingUser` | 1. Normal browsing | Homepage, product list, product details |
| `SearchUser` | 2. Product search | Text search, categories, category filter + sorting |
| `OrderUser` | 3. Order activity | Views products (cart is client-side), opens checkout, submits a demo order, fetches the confirmation |
| `MixedWorkloadUser` | 4. Mixed workload | Homepage, listings, search, details, health check, occasional orders |

Request names are grouped (e.g. `/api/products/[id]`) so the statistics table has
one row per endpoint instead of one row per product.

`409 Insufficient stock` responses on orders are counted as **successful** business
responses (they are correct behaviour when stock runs out after many orders).
To restore the original stock, reset the database (this deletes all orders):

```bash
docker compose down -v && docker compose up --build -d
```

## Setup (once)

```bash
cd load-testing
python3.11 -m venv .venv            # or: uv venv --python 3.11 .venv
source .venv/bin/activate
pip install -r requirements.txt
locust --version
```

## Run with the web UI

```bash
# Start the website first:  docker compose up --build -d   (from the project root)
cd load-testing && source .venv/bin/activate
locust -f locustfile.py --host http://localhost
```

Open <http://localhost:8089>, choose the user classes (scenarios), number of users
and spawn rate, then press **Start**. The *Charts* tab shows RPS and response times
live; *Download Data* exports CSV/HTML reports.

Pick a single scenario from the command line by naming its class:

```bash
locust -f locustfile.py --host http://localhost SearchUser
```

## Run headless (repeatable, for the report)

One scenario:

```bash
locust -f locustfile.py --host http://localhost MixedWorkloadUser \
  --headless -u 50 -r 5 -t 2m \
  --csv results/mixed --html results/mixed.html
```

All four scenarios in sequence (arguments: host, users, spawn rate, duration):

```bash
./run_scenarios.sh http://localhost 20 5 1m
```

Reports are saved to `load-testing/results/<timestamp>/` (ignored by git), and a
summary table is printed from the `Aggregated` row of each `*_stats.csv`.

Against EC2, replace the host: `./run_scenarios.sh http://<EC2-public-IP> 20 5 2m`.
Run Locust from your laptop (not from the EC2 instance itself) so the load generator
does not compete with the website for CPU.

## Suggested test plan

| Test | Users | Spawn rate | Duration | Purpose |
|---|---|---|---|---|
| Smoke | 5 | 1/s | 1 min | Scripts and site work |
| Normal load | 25 | 5/s | 5 min | Typical traffic baseline |
| Peak load | 100 | 10/s | 5 min | Behaviour under heavy traffic |
| Spike | 200 | 50/s | 2 min | Sudden burst; watch errors and p95 |

Keep everything else constant between runs (same machine, same instance type,
fresh database) so results are comparable.

## Recording results

Locust reports every metric the project needs. Map them as follows:

| Required metric | Where Locust reports it |
|---|---|
| Requests per second | `Requests/s` column (Aggregated row) |
| Average response time | `Average Response Time` (ms) |
| Median response time | `Median Response Time` (ms) |
| 95th percentile | `95%` column (ms) |
| Failure percentage | `Failure Count / Request Count x 100` |
| Total requests | `Request Count` |

Fill this table **only with numbers from your own runs** (copy from
`summarize_results.py` output). Do not estimate or invent values.

| Environment | Scenario | Users | Duration | Total requests | Req/s | Avg (ms) | Median (ms) | p95 (ms) | Failure % |
|---|---|---|---|---|---|---|---|---|---|
| Local Docker (M1) | BrowsingUser | | | | | | | | |
| Local Docker (M1) | SearchUser | | | | | | | | |
| Local Docker (M1) | OrderUser | | | | | | | | |
| Local Docker (M1) | MixedWorkloadUser | | | | | | | | |
| AWS EC2 (type: ___) | MixedWorkloadUser | | | | | | | | |

While a test runs, also watch `http://localhost/api/stats`, `http://localhost/api/metrics`
and (optionally) Grafana at <http://localhost:3000> to see the server side of the same load.

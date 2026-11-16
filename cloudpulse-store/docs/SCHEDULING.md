# Request scheduling on the website

This document describes how the CloudPulse scheduling algorithms are applied to the CloudPulse
Store's **own HTTP traffic**, and what was measured locally on 14 November 2026 (Mac M1, 8 GB,
Docker via Colima with 2 CPUs / 3 GB; AWS EC2 was stopped, so nothing here ran in the cloud).

## 1. What changed

| Before | After |
|---|---|
| 1 backend container | 3 backend replicas `backend-1/2/3` (B1/B2/B3) with CPU quotas 0.75 / 0.45 / 0.30 and 4 / 2 / 2 concurrent request slots |
| Nginx `/api/*` → backend | Nginx `/api/*` → **scheduling gateway** → replica chosen by the active algorithm |
| — | `/gateway/*` API on the gateway's own port <http://localhost:8090> (stats, recent, events, runs, algorithm switch, Prometheus metrics) and a Grafana dashboard. No extra UI: the project's scheduling dashboard remains the Streamlit one of the live cluster. The shop website is unchanged for its users. |
| Prometheus scraped `backend:8000` | scrapes `backend-1/2/3` and `gateway`; new Grafana dashboard *Request Scheduling Gateway* |

The algorithm classes come from `cloudpulse-scheduler/src/schedulers` **unchanged** (the same
code as the simulator and the live task cluster). The gateway's `dispatcher.py` provides the
bridge: one replica = one mirror `Worker` (capacity, weight, slots), one HTTP request = one
`Task` whose estimated duration is the learned service time of its route (EWMA, started from
defaults). The mirror's queue holds the requests in flight, so `can_accept()`, `estimated_load()`
and `weight` work exactly as in the simulator. When all slots are busy, requests wait in the
gateway: RR/WRR/LL keep a FIFO backlog and place the head as soon as any replica can accept;
SJF/FCFS keep a central queue and release the shortest (SJF) or oldest (FCFS) request to the
fastest free replica. A request waiting more than 10 s gets `503`.

Failure handling: replicas are probed every 2 s; a replica that refuses connections is marked
unavailable immediately, the affected request is re-dispatched (only if it never reached the
replica, so nothing executes twice), and the replica rejoins when the probe succeeds again.
Demo: `docker compose kill backend-2`, watch `curl localhost:8090/gateway/events`, then `docker compose start backend-2`.

## 2. Measurements (REAL HTTP traffic, single Docker host)

Same Locust scenario `MixedWorkloadUser` (browse, search, filter, order) run once per algorithm
by `load-testing/compare_algorithms.sh`; the gateway run was archived after each algorithm.
*Avg / Median / p95* are Locust's end-to-end latencies (includes Nginx and static pages);
*Gateway queue wait* and *Backend service* come from the gateway for API requests only.

### 40 users (≈ 30 req/s, light load)

| Algorithm | Requests | Fail % | Req/s | Avg ms | Median ms | p95 ms | Gateway queue wait ms | Backend service ms | Share B1 / B2 / B3 % |
|---|---|---|---|---|---|---|---|---|---|
| RR | 1356 | 0.00 | 30.72 | 10.8 | 8 | 32 | 0.2 | 8.9 | 34 / 33 / 33 |
| WRR | 1359 | 0.00 | 30.71 | 9.8 | 7 | 24 | 0.1 | 7.7 | 50 / 30 / 20 |
| LL | 1383 | 0.00 | 31.19 | 22.3 | 8 | 61 | 1.4 | 18.2 | 79 / 16 / 5 |
| SJF | 1324 | 0.00 | 29.96 | 9.9 | 6 | 29 | 0.2 | 8.2 | 98 / 1 / 1 |
| FCFS (control) | 1349 | 0.00 | 30.58 | 7.5 | 6 | 17 | 0.1 | 5.9 | 98 / 1 / 1 |

### 150 users (≈ 112 req/s, replicas busy)

| Algorithm | Requests | Fail % | Req/s | Avg ms | Median ms | p95 ms | Gateway queue wait ms | Backend service ms | Share B1 / B2 / B3 % |
|---|---|---|---|---|---|---|---|---|---|
| RR | 4958 | 0.00 | 112.50 | 9.1 | 5 | 35 | 1.8 | 6.4 | 34 / 33 / 33 |
| WRR | 4924 | 0.00 | 111.65 | 8.2 | 5 | 33 | 1.5 | 5.6 | 50 / 30 / 20 |
| LL | 5004 | 0.00 | 113.45 | 7.2 | 5 | 22 | 1.2 | 4.7 | 76 / 19 / 5 |
| SJF | 4901 | 0.00 | 111.08 | 17.9 | 5 | 70 | 7.7 | 10.1 | 93 / 4 / 3 |
| FCFS (control) | 4920 | 0.00 | 111.52 | 8.5 | 5 | 27 | 2.2 | 5.5 | 96 / 2 / 2 |

Gateway run summaries (API requests only, 150 users):

| Algorithm | Completed | Avg total ms | p95 total ms | Avg queue wait ms |
|---|---|---|---|---|
| RR | 3272 | 8.2 | 39.1 | 1.8 |
| WRR | 3285 | 7.1 | 33.7 | 1.5 |
| LL | 3316 | 5.9 | 24.5 | 1.2 |
| SJF | 3226 | 17.8 | 69.8 | 7.7 |
| FCFS (control) | 3237 | 7.7 | 42.1 | 2.2 |

## 3. Findings

1. **Least Loaded is the best choice for the website** at both load levels: lowest average and
   p95 latency and the highest throughput. It sends ≈ 76 % of requests to the fast replica B1
   and only ≈ 5 % to B3, because its load estimate divides by capacity.
2. **RR is the worst of the per-replica-queue algorithms**: an equal 33/33/33 split overloads the
   slowest replica B3 (p95 35–39 ms vs 22–24 ms for LL). **WRR** (50/30/20) sits in between —
   it follows the static capacity ratio but ignores what is actually in flight.
3. **SJF is not suitable for a web server under sustained load.** It orders the central queue
   by estimated service time, so cheap requests (health, categories, product by id) always jump
   ahead of expensive ones (`POST /api/orders`, product listings). With traffic arriving
   continuously the expensive requests starve: p95 rises to ≈ 70 ms and the average queue wait
   is 4–6× that of the other algorithms, although the median is unchanged (5 ms). This is the
   textbook SJF starvation effect and the opposite of what the batch simulator showed, where the
   workload is finite and SJF minimises average waiting time.
4. **FCFS (control)** performs like WRR here: a central FIFO queue released to the fastest free
   replica is a reasonable policy, but it uses no load information and puts ≈ 96 % of requests
   on B1 (its 4 slots were rarely all busy).
5. At light load (40 users) the queues are almost always empty, so all algorithms give similar
   latency; the differences only show when replicas are busy, exactly as in the simulator.

## 4. Limitations

* One run of 45 s per algorithm on a shared laptop; no repetitions, no confidence intervals.
  Re-run `compare_algorithms.sh` several times (or with `ALGORITHMS="least_loaded round_robin"`)
  before quoting precise numbers.
* The three replicas share one SQLite file (WAL) on one host; the heterogeneity is CPU quota,
  not separate machines. The same compose file runs unchanged on an EC2 host.
* Service-time estimates are per route (EWMA); SJF therefore cannot distinguish a cheap from an
  expensive product search.
* Slots (4/2/2) are a static concurrency model; a backend could serve more concurrent requests
  than its slot count, which is deliberately conservative so that queueing (and therefore the
  scheduling decision) actually happens.

## 5. How to reproduce

```bash
cd cloudpulse-store && docker compose up --build -d          # site + 3 replicas + gateway
curl -s localhost:8090/gateway/stats | python3 -m json.tool      # gateway numbers (JSON)
cd load-testing && source .venv/bin/activate
./compare_algorithms.sh http://localhost 150 30 45s MixedWorkloadUser
```

## 6. Driving the website from the Streamlit dashboard (added 14 Nov 2026)

The Streamlit dashboard (`cloudpulse-scheduler`, page **Website workload**) is now the traffic
source for the website. It controls a small workload generator service
([`loadgen/`](../loadgen/README.md)) inside the store stack:

```
Streamlit ─▶ loadgen ─▶ Nginx (website) ─▶ scheduling gateway ─▶ backend-1 / 2 / 3
```

On the page you choose the gateway algorithm, the number of requests, the arrival rate, the
shopper behaviour (mix) and a seed, then press **Start**. The page shows progress, OK/errors,
achieved req/s and p50/p95 latency, the per-replica table (health, slots, in flight, share,
wait and service time, CPU and memory from Prometheus), the latest requests with the replica
that served each one, request types, gateway events and a comparison table of finished runs.
Grafana's **Request Scheduling Gateway** dashboard has a matching section, *Website workload
(sent from the Streamlit dashboard)*, with run progress, client-side req/s, error rate,
p50/p95 latency and requests by type. A simulated outage of one replica can be started from the
same page (`POST /gateway/backends/{id}/outage`).

### Measured on the Mac (one Docker host, Colima, 14 Nov 2026)

Same workload for each algorithm: 3000 requests, mix `mixed`, seed 42, 200 req/s, at most 200 in
flight. Latency is end-to-end as seen by the client (through Nginx and the gateway).

| Algorithm | OK | Achieved req/s | Avg ms | p95 ms | p99 ms | Avg gateway wait ms | B1 / B2 / B3 share |
|---|---|---|---|---|---|---|---|
| Round Robin | 3000 / 3000 | 198.0 | 18.2 | 75.7 | 149.3 | 0.93 | 34.5 / 33.1 / 32.4 % |
| Weighted Round Robin | 3000 / 3000 | 198.5 | 14.3 | 50.7 | 130.0 | 0.25 | 50.4 / 29.3 / 20.3 % |
| Least Loaded | 3000 / 3000 | 198.6 | 8.5 | 29.3 | 53.9 | 0.06 | 62.0 / 27.2 / 10.8 % |

- At 200 req/s the slow replicas (0.45 and 0.30 CPU) saturate under Round Robin; Least Loaded
  sends most traffic to B1 and cuts p95 latency by about 60 % compared with Round Robin.
- At 25 req/s (1000 requests, same seed) all algorithms gave p95 ≈ 17–19 ms: the site is
  under-loaded, so the choice of replica hardly matters. Use ≥ 150 req/s to show differences.
- **Graceful outage** (gateway stops routing to a replica) during a 1000-request Least Loaded run
  at 25 req/s: B1 out for 20 s; B2/B3 took its traffic, B1 rejoined, all 1000 requests
  succeeded (0 errors). Nothing is killed, so no request can fail.
- **Real crash** (dashboard *Real crash*: the replica's process is killed and its port stays
  closed for 15 s) during a 6000-request Least Loaded run at 200 req/s:

  | Seconds into the gateway run | Event |
  |---|---|
  | 53.8 | crash requested for B1 (process killed) |
  | 54.0 | B1 marked unavailable (connection refused); 2 requests re-dispatched to B2/B3 |
  | 68.9 | B1 back (Docker restart + 15 s downtime), health probe marks it recovered |

  Result: 5998 / 6000 OK, **2 server errors** (502: requests B1 was serving when it died; the
  gateway does not resend those because the request may already have been processed, e.g. an
  order). p95 rose to 1.6 s and the slowest request took 7.4 s: without B1 only 0.75 of the
  1.5 CPU cores remain, so at 200 req/s the remaining replicas are overloaded and requests queue
  until B1 returns. Errors stay near zero; the cost of the failure shows up as latency.
- Each configuration was run once; these numbers show the behaviour, not a statistical result.
  For averages over seeds, repeat with seeds 1–5 (same settings) and compare the means.

# Deploying the live scheduler cluster + dashboard on EC2

The code reaches EC2 only through GitHub (`git clone https://github.com/mohana9985/CloudPulse.git`).
Every IP and per-machine setting lives only in `cloudpulse-scheduler/.env` (created from the
committed template [`../.env.example`](../.env.example), ignored by Git). `ec2-deploy-live.sh`
takes no IPs as arguments; it reads `.env`, runs `git pull` at the repository root (skip with
`--no-pull`) and creates `.env` from the template if it is missing.

| Layout | Status | Guide |
|---|---|---|
| **A. Two instances**: store on EC2 #1, this stack (coordinator, 3 workers, Streamlit) on EC2 #2 | **Current plan** (the earlier store instance was deleted on 2026-11-16; both instances are created new) | [`../../cloudpulse-store/docs/AWS_TWO_EC2.md`](../../cloudpulse-store/docs/AWS_TWO_EC2.md) |
| B. One instance running the store and this stack | Alternative | below |

## A. Dashboard instance (two-EC2 setup)

```bash
ssh -i ~/.ssh/cloudpulse-key.pem ubuntu@<EC2-2-public-IP>     # Windows PowerShell: -i $HOME\.ssh\cloudpulse-key.pem
git clone https://github.com/mohana9985/CloudPulse.git cloudpulse
cd cloudpulse/cloudpulse-store && bash deployment/aws/ec2-setup.sh   # Docker; log out and in again
cd ~/cloudpulse/cloudpulse-scheduler
cp .env.example .env && chmod 600 .env
nano .env      # uncomment the Two-EC2 block: COMPOSE_FILE, STORE_HOST=<store private IP>, DASHBOARD_BIND, COORDINATOR_BIND
bash deployment/ec2-deploy-live.sh
```

With `COMPOSE_FILE=compose.yaml:compose.two-host.yaml` in `.env` the script starts coordinator +
workers + dashboard, checks that the store's gateway (8090), loadgen (8095) and Prometheus (9090)
answer at `STORE_HOST`, and stops if `STORE_HOST` is still the placeholder. Open
`http://<EC2-2-public-IP>:8501` (security group: 8501 from your IP only; 8100 only from the store's
security group so its Prometheus can scrape the coordinator).

## Resource budget (this stack)


| Service | Memory limit | Measured use (Mac, Colima) | CPU |
|---|---|---|---|
| coordinator | 192 MB | ~39 MB | shared |
| worker-1/2/3 | 128 MB each | ~40 MB each | quota 0.75 / 0.45 / 0.30 |
| dashboard (optional) | 320 MB | ~51 MB idle | shared |

Images are arm64-compatible (`python:3.11-slim`). Disk: ~250 MB service image, ~850 MB dashboard
image. Check `df -h` first; skip the dashboard on a small disk.

## B. Single instance (store + scheduler on one EC2)

No extra ports are opened: the coordinator (8100) and dashboard (8501) bind to `127.0.0.1` and are
reached through an SSH tunnel, like Grafana and Prometheus. Keep the Two-EC2 blocks in both
`.env` files commented out.

```bash
ssh -i <path-to-key>.pem ubuntu@<EC2-IP>
free -m && df -h /                       # check headroom first
cd ~/cloudpulse && git pull --ff-only    # repository cloned from GitHub; .env files created from .env.example
cd cloudpulse-store
bash deployment/aws/deploy.sh --monitoring               # website, 3 replicas, gateway, loadgen, Prometheus, Grafana
cd ../cloudpulse-scheduler
bash deployment/ec2-deploy-live.sh --with-dashboard      # coordinator, 3 workers, Streamlit (joins the store network)
```

The full system measured on the Mac uses about 710 MB of memory in total (13 containers), so the
2 GB t4g.small is enough. `--with-dashboard` applies `compose.monitoring.yaml`, because the
dashboard's *Website workload* page talks to the gateway, the loadgen and Prometheus on the
store network. `--with-monitoring` alone (no dashboard) only adds the coordinator scrape.

For Prometheus to scrape the coordinator, the store's Prometheus must be restarted once to load the
new scrape job: `cd ~/cloudpulse/cloudpulse-store && docker compose --profile monitoring up -d --force-recreate prometheus grafana`.

From your computer (macOS/Linux):

```bash
ssh -i <path-to-key>.pem -N -L 8100:127.0.0.1:8100 -L 8501:127.0.0.1:8501 -L 3000:127.0.0.1:3000 ubuntu@<EC2-IP>
open http://localhost:8501     # dashboard: "Website workload" (default) and "Compute cluster"
open http://localhost:3000     # Grafana -> CloudPulse -> "Request Scheduling Gateway" / "Live Cluster"
```

Windows (PowerShell):

```powershell
ssh -i $HOME\.ssh\cloudpulse-key.pem -N -L 8100:127.0.0.1:8100 -L 8501:127.0.0.1:8501 -L 3000:127.0.0.1:3000 ubuntu@<EC2-IP>
# in a second window:
Start-Process http://localhost:8501
Start-Process http://localhost:3000
```

Run the experiments on the instance (either layout; on the dashboard instance in layout A) with a distinct setup label:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-live.txt
.venv/bin/python -m live.experiments.run_live grid --setup ec2-single-host --experiment-id live-ec2 --sizes 30 60 --seeds 1 2 3
.venv/bin/python -m live.experiments.live_charts live-ec2
```

Note: `SECONDS_PER_UNIT` was calibrated on the Mac. On Graviton re-run
`docker compose exec worker-1 python -m live.calibrate`; estimates only affect LL/SJF ordering,
never the measured times.

## Rollback

```bash
cd ~/cloudpulse/cloudpulse-scheduler
docker compose down        # uses COMPOSE_FILE from .env (layout A); layout B: add -f compose.yaml -f compose.monitoring.yaml
docker image rm cloudpulse-live:latest cloudpulse-live-dashboard:latest   # free disk
```

The store is not modified by this procedure apart from one extra Prometheus scrape job, which
shows as "down" and is harmless when the scheduler is stopped. To remove it, revert
`cloudpulse-store/monitoring/prometheus/prometheus.yml` and recreate Prometheus.

## Cost

Layout A bills two instances, layout B one; nothing else (no load balancers, Elastic IPs or extra
volumes). Instances are billed while running: stop them when not demonstrating. Cost comparison
per configuration: [`../docs/cost_analysis.md`](../docs/cost_analysis.md).

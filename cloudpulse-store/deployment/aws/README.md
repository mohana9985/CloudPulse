# `deployment/aws/` — EC2 scripts and host configuration

Scripts that run **on an AWS EC2 Ubuntu instance**. They never create AWS resources, never
read AWS credentials and never spend money; you create, stop and terminate the instance yourself.

| File | Run | What it does |
|---|---|---|
| `ec2-setup.sh` | Once, as the `ubuntu` user | Updates packages, installs Docker Engine + Compose plugin from Docker's official apt repository, adds the user to the `docker` group, configures container log rotation (10 MB × 3), creates a 2 GB swap file when RAM < 2 GB |
| `deploy.sh` | Every deploy/update | `git pull --ff-only` at the repository root (works in the monorepo), creates `.env` from `.env.example` if missing (`ENVIRONMENT=production`, `chmod 600`), replaces the placeholder `GRAFANA_ADMIN_PASSWORD` with a random one, stops if two-EC2 mode is on in `.env` but `SCHEDULER_HOST` is still the placeholder, `docker compose up --build -d` (compose reads `COMPOSE_FILE` / `COMPOSE_PROFILES` from `.env`), waits up to 60 s for `/api/ready`, prints the public URLs from the instance metadata service (IMDSv2). Options: `--no-pull`, `--monitoring` |
| `nginx-site.conf` | Optional, host Nginx | HTTPS reverse proxy (Let's Encrypt) in front of the container bound to `127.0.0.1:8080`; replace `store.example.com` with your domain |
| `tunnel.sh` / `tunnel.ps1` | On YOUR computer (macOS / Windows) | Opens SSH tunnels to the AWS instances on **different local ports from local Docker**, all read from `.env` (`AWS_*`): Grafana `localhost:3001`, Prometheus `9091`, gateway `8091`, loadgen `8096`, coordinator `8101` (local Docker keeps 3000 / 9090 / 8090 / 8095 / 8100). Ctrl+C closes them |

```bash
# on the instance, inside the cloned repository
cd ~/cloudpulse/cloudpulse-store
bash deployment/aws/ec2-setup.sh          # then log out and back in
cp .env.example .env && nano .env         # all IPs/passwords/settings go here, never in Git
bash deployment/aws/deploy.sh             # pulls from GitHub; add --monitoring for Prometheus + Grafana
```

## Port map: local Docker vs AWS

Every host port is a `.env` setting. Local Docker and the AWS tunnel use different ports, so both can run at the same time.

| Service | Local Docker (`.env`) | AWS from your computer (`.env`) | On the EC2 itself |
|---|---|---|---|
| Store website | `http://localhost:80` (`HTTP_PORT`) | `http://<EC2-1-public-IP>/` (no tunnel) | 80 |
| Streamlit dashboard | `http://localhost:8501` (`DASHBOARD_PORT`, scheduler `.env`) | `http://<EC2-2-public-IP>:8501` (no tunnel) | 8501 |
| Grafana | `3000` (`GRAFANA_PORT`) | `3001` (`AWS_GRAFANA_LOCAL_PORT`) | 3000 |
| Prometheus | `9090` (`PROMETHEUS_PORT`) | `9091` (`AWS_PROMETHEUS_LOCAL_PORT`) | 9090 |
| Gateway API | `8090` (`GATEWAY_PORT`) | `8091` (`AWS_GATEWAY_LOCAL_PORT`) | 8090 |
| Loadgen API | `8095` (`LOADGEN_PORT`) | `8096` (`AWS_LOADGEN_LOCAL_PORT`) | 8095 |
| Coordinator | `8100` (`COORDINATOR_PORT`, scheduler `.env`) | `8101` (`AWS_COORDINATOR_LOCAL_PORT`) | 8100 |

```bash
# macOS, from cloudpulse-store/ (fill AWS_STORE_PUBLIC_IP etc. in .env first)
bash deployment/aws/tunnel.sh
```

```powershell
# Windows PowerShell, from cloudpulse-store\
powershell -ExecutionPolicy Bypass -File deployment\aws\tunnel.ps1
```

Security: open SSH (22) to your own IP only and HTTP/HTTPS (80/443) publicly. Never open 8000,
9090 or 3000 to the internet; Prometheus and Grafana bind to `127.0.0.1` and are reached through an
SSH tunnel. Two-EC2 setup: 8090/8095/9090 open **only** to the dashboard instance's security group
([`../../docs/AWS_TWO_EC2.md`](../../docs/AWS_TWO_EC2.md)).
Keep the `.pem` key outside the repository (macOS: `~/.ssh/`, `chmod 400`; Windows: `$HOME\.ssh\`,
`icacls <key> /inheritance:r /grant:r "$($env:USERNAME):R"`). These scripts run on the Ubuntu
instance, so the commands are the same whether you connect from macOS or Windows.

Overview: [`../README.md`](../README.md) · Two-EC2 guide: [`../../docs/AWS_TWO_EC2.md`](../../docs/AWS_TWO_EC2.md) · Single instance: [`../../docs/AWS_DEPLOYMENT.md`](../../docs/AWS_DEPLOYMENT.md)

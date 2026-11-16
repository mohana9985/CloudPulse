# Deployment

Files used to run CloudPulse Store on an **AWS EC2 Ubuntu** instance. The code reaches the
instance only through GitHub (`git clone` / `git pull` of the monorepo
<https://github.com/mohana9985/CloudPulse>); every IP, password and per-machine setting lives only in
`cloudpulse-store/.env` (created from the committed template `.env.example`, ignored by Git).

| Guide | When |
|---|---|
| [`../docs/AWS_TWO_EC2.md`](../docs/AWS_TWO_EC2.md) | **Current plan**: two new instances — store (this folder) + dashboard/scheduler (`cloudpulse-scheduler`) |
| [`../docs/AWS_DEPLOYMENT.md`](../docs/AWS_DEPLOYMENT.md) | Single instance, plus details on SSH, HTTPS, costs, troubleshooting |

| File | Run where | What it does |
|---|---|---|
| `aws/ec2-setup.sh` | On the EC2 instance, once | Installs Docker Engine + Compose plugin, enables log rotation, adds swap on small instances |
| `aws/deploy.sh` | On the EC2 instance, every deploy/update | `git pull` at the repository root, creates `.env` from `.env.example` if missing, replaces the placeholder Grafana password with a random one, checks the two-EC2 settings in `.env`, `docker compose up --build -d`, waits for `/api/ready`, prints URLs |
| `aws/nginx-site.conf` | Host Nginx, optional | Reverse proxy for HTTPS with a domain + Let's Encrypt certificate |

These scripts **never create AWS resources** and never spend money. You create the
EC2 instance yourself in the AWS console and stop/terminate it yourself. They take no IPs or
passwords as arguments; only `--no-pull` and `--monitoring` (same as `COMPOSE_PROFILES=monitoring`
in `.env`).

## Quick version

```bash
# On your computer (macOS/Linux; Windows PowerShell: ssh -i $HOME\.ssh\cloudpulse-key.pem ...)
ssh -i ~/.ssh/cloudpulse-key.pem ubuntu@<EC2-public-IP>

# On the instance (first time)
git clone https://github.com/mohana9985/CloudPulse.git cloudpulse
cd cloudpulse/cloudpulse-store
bash deployment/aws/ec2-setup.sh
exit                                                 # log out so the docker group applies

ssh -i ~/.ssh/cloudpulse-key.pem ubuntu@<EC2-public-IP>
cd cloudpulse/cloudpulse-store
cp .env.example .env && chmod 600 .env && nano .env  # two EC2s: uncomment the Two-EC2 block
bash deployment/aws/deploy.sh                        # pulls, builds, starts

# Every update later: push to GitHub from your computer, then on the instance
bash deployment/aws/deploy.sh
```

Then open `http://<EC2-public-IP>/`.

Windows: protect the downloaded key once with
`icacls $HOME\.ssh\cloudpulse-key.pem /inheritance:r /grant:r "$($env:USERNAME):R"` (the
equivalent of `chmod 400`); the `ssh` commands are otherwise identical in PowerShell.

## Ports

| Port | Open to | Why |
|---|---|---|
| 22 (SSH) | **Your IP only** (`x.x.x.x/32`) | Administration |
| 80 (HTTP) | `0.0.0.0/0` | Website + API + monitoring endpoints |
| 443 (HTTPS) | `0.0.0.0/0` | Only if you enable HTTPS |

Two-EC2 setup ([`../docs/AWS_TWO_EC2.md`](../docs/AWS_TWO_EC2.md)): additionally 8090 (gateway), 8095
(loadgen) and 9090 (Prometheus), with the **dashboard instance's security group** as the source —
never `0.0.0.0/0`.

Never open 8000 (backend), 9090 (Prometheus) or 3000 (Grafana) to the internet. The backend is
not published at all, and Prometheus/Grafana bind to `127.0.0.1` only; reach them
with an SSH tunnel:

```bash
ssh -i ~/.ssh/cloudpulse-key.pem -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 ubuntu@<EC2-public-IP>
```

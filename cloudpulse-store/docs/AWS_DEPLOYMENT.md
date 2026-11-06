# AWS EC2 Deployment Guide

This guide deploys CloudPulse Store on one Ubuntu EC2 instance with Docker Compose.
Nothing here is automated against your AWS account: **you** create, stop and
terminate resources in the AWS console. Do not assume Free Tier eligibility —
check the [EC2 pricing page](https://aws.amazon.com/ec2/pricing/on-demand/) for your region.

```
Internet --> Security Group (80/443 open, 22 = your IP) --> EC2 Ubuntu
                                                            └─ Docker Compose
                                                               ├─ frontend (Nginx :80, public)
                                                               └─ backend  (FastAPI :8000, internal only)
                                                                   └─ SQLite on Docker volume
```

## 1. Create the EC2 instance

AWS Console -> **EC2** -> **Launch instance**:

| Setting | Recommended value |
|---|---|
| Name | `cloudpulse-store` |
| AMI | **Ubuntu Server 24.04 LTS** (or 22.04 LTS) |
| Architecture | 64-bit (Arm) for `t4g.*`, 64-bit (x86) for `t3.*` — both work |
| Instance type | `t4g.small` or `t3.small` (2 GB RAM). `*.micro` (1 GB) works; the setup script adds swap |
| Key pair | Create new -> RSA -> `.pem` -> download `cloudpulse-key.pem` |
| Network | Default VPC, public subnet, **Auto-assign public IP: Enable** |
| Security group | Create new (see step 8) |
| Storage | 20 GiB gp3 |

Keep the same instance type for all performance tests so results are comparable.

## 2. Connect through SSH

```bash
mv ~/Downloads/cloudpulse-key.pem ~/.ssh/
chmod 400 ~/.ssh/cloudpulse-key.pem
ssh -i ~/.ssh/cloudpulse-key.pem ubuntu@<EC2-public-IP>
```

The public IPv4 address is shown on the instance's *Details* tab.

## 3. Install Docker Engine and Docker Compose

Get the project onto the instance first (step 4), then:

```bash
cd ~/cloudpulse/cloudpulse-store      # Option B (rsync) below: cd ~/cloudpulse-store
bash deployment/aws/ec2-setup.sh
exit                                  # log out so the "docker" group takes effect
ssh -i ~/.ssh/cloudpulse-key.pem ubuntu@<EC2-public-IP>
docker compose version                # should work without sudo
```

The script installs Docker from Docker's official apt repository, enables log
rotation and creates a 2 GB swap file on instances with less than 2 GB RAM.

## 4. Transfer or clone the project

**Option A — Git (recommended):**

```bash
git clone https://github.com/<your-account>/cloudpulse.git ~/cloudpulse
cd ~/cloudpulse/cloudpulse-store
```

The `cloudpulse` repository contains both CloudPulse Store and CloudPulse Scheduler; the store is
the `cloudpulse-store/` subfolder. Because `.git` is at the repository root, `deploy.sh` does not
pull by itself — run `git -C ~/cloudpulse pull --ff-only` before `bash deployment/aws/deploy.sh`.

**Option B — copy from your Mac** (no Git hosting needed), run on the Mac:

```bash
rsync -avz --exclude node_modules --exclude .venv --exclude dist --exclude '.env' \
  --exclude '*.db' -e "ssh -i ~/.ssh/cloudpulse-key.pem" \
  ./cloudpulse-store/ ubuntu@<EC2-public-IP>:~/cloudpulse-store/
```

## 5. Configure environment variables

```bash
cd ~/cloudpulse/cloudpulse-store      # Option B (rsync): cd ~/cloudpulse-store
cp .env.example .env
nano .env
```

Set at least:

```
ENVIRONMENT=production
GRAFANA_ADMIN_PASSWORD=<long random value>     # e.g. output of: openssl rand -hex 16
```

`deploy.sh` creates `.env` automatically (production mode, random Grafana password)
if it does not exist. `.env` is in `.gitignore`; never commit it. Protect it with `chmod 600 .env`.

## 6. Build Docker images & 7. Start containers

```bash
bash deployment/aws/deploy.sh             # git clone users
bash deployment/aws/deploy.sh --no-pull   # rsync/scp users
```

This runs `docker compose up --build -d`, waits for `/api/ready` and prints the URLs.
Manual equivalent:

```bash
docker compose up --build -d
docker compose ps
```

## 8. Configure the security group

EC2 -> Security Groups -> your group -> **Edit inbound rules**:

| Type | Port | Source | Notes |
|---|---|---|---|
| SSH | 22 | **My IP** (`x.x.x.x/32`) | Never `0.0.0.0/0` |
| HTTP | 80 | `0.0.0.0/0` (and `::/0`) | Website, API, health, metrics |
| HTTPS | 443 | `0.0.0.0/0` (and `::/0`) | Only if you enable HTTPS (step 15) |

Do **not** add rules for 8000, 9090 or 3000. The backend port is not published by
Docker at all, and Prometheus/Grafana listen on `127.0.0.1` only. SQLite lives inside
a Docker volume and is never served (Nginx also denies `*.db`/`*.sqlite` URLs).

If your home IP changes, update the SSH rule ("My IP" again).

## 9. Access the website

| URL | |
|---|---|
| `http://<EC2-public-IP>/` | Website |
| `http://<EC2-public-IP>/api/docs` | API docs |
| `http://<EC2-public-IP>/api/health` | Health |
| `http://<EC2-public-IP>/api/metrics` | Prometheus metrics |
| `http://<EC2-public-IP>/api/stats` | JSON statistics |

The public IP **changes every time the instance is stopped and started**. For a fixed
address allocate an Elastic IP (note: public IPv4 addresses, including Elastic IPs, are billed).

## 10. Check application health

```bash
curl -s http://localhost/api/health
curl -s http://localhost/api/ready
docker compose ps                     # STATUS column shows (healthy)
```

From your Mac: `curl -s http://<EC2-public-IP>/api/health`.

## 11. View logs

```bash
docker compose logs -f                # everything
docker compose logs -f --tail 100 backend
docker compose logs -f frontend       # Nginx access log (every request)
docker stats                          # live container CPU / memory
free -h; df -h; uptime                # host memory, disk, load
```

## 12. Update the application

```bash
cd ~/cloudpulse/cloudpulse-store
git -C ~/cloudpulse pull --ff-only   # monorepo: pull at the repository root
bash deployment/aws/deploy.sh         # rebuild + restart, data is kept
```

(rsync users: re-run the rsync command from step 4, then `bash deployment/aws/deploy.sh --no-pull`.)

## 13. Stop and restart services

```bash
docker compose stop                   # stop containers, keep them
docker compose start                  # start again
docker compose restart                # restart
docker compose down                   # remove containers (database volume kept)
docker compose up -d                  # start again without rebuilding
```

Containers use `restart: unless-stopped` and Docker is enabled at boot, so the
site comes back automatically after an instance reboot.

Optional monitoring stack, viewed through an SSH tunnel:

```bash
bash deployment/aws/deploy.sh --monitoring
# on your Mac:
ssh -i ~/.ssh/cloudpulse-key.pem -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 ubuntu@<EC2-public-IP>
# then open http://localhost:3000 and http://localhost:9090 on the Mac
```

## 14. Safely shut down or terminate

1. Save anything you need (Locust reports, screenshots). Optional database backup:
   ```bash
   docker compose exec backend python -c "import sqlite3; s=sqlite3.connect('/app/data/cloudpulse.db'); d=sqlite3.connect('/app/data/backup.db'); s.backup(d)"
   docker compose cp backend:/app/data/backup.db ./backup.db
   ```
2. `docker compose down`
3. AWS Console -> EC2 -> Instances -> select instance:
   * **Stop instance** — compute billing stops; the EBS volume (disk) is still billed. Public IP is released.
   * **Terminate instance** — deletes the instance (and its root volume by default). Billing stops. Irreversible.
4. Also release any **Elastic IP** and delete unused **EBS snapshots/volumes** — they are billed even with no instance running.

## 15. Enabling HTTPS (domain + TLS certificate)

Browsers only trust certificates for a domain name, not a bare IP. You need a domain
(e.g. from Route 53 or any registrar) with an **A record** pointing to the instance's
Elastic IP.

1. Move the container behind a host-level Nginx — in `.env`:
   ```
   HTTP_BIND=127.0.0.1
   HTTP_PORT=8080
   ```
   then `docker compose up -d`.
2. Install Nginx and Certbot on the host:
   ```bash
   sudo apt-get install -y nginx certbot python3-certbot-nginx
   ```
3. Install the site config and set your domain:
   ```bash
   sudo cp deployment/aws/nginx-site.conf /etc/nginx/sites-available/cloudpulse
   sudo sed -i 's/store.example.com/your.domain.com/g' /etc/nginx/sites-available/cloudpulse
   sudo ln -s /etc/nginx/sites-available/cloudpulse /etc/nginx/sites-enabled/cloudpulse
   sudo rm -f /etc/nginx/sites-enabled/default
   sudo nginx -t && sudo systemctl reload nginx
   ```
4. Open port 443 in the security group, then obtain the certificate:
   ```bash
   sudo certbot --nginx -d your.domain.com --redirect
   sudo certbot renew --dry-run       # renewal is automatic via a systemd timer
   ```
5. Visit `https://your.domain.com`. HTTP now redirects to HTTPS, and the original
   scheme is forwarded to the app via `X-Forwarded-Proto`.

## AWS cost considerations

You pay for (check current prices for your region; Free Tier is **not** assumed):

| Resource | Billed when | How to avoid waste |
|---|---|---|
| EC2 instance hours | Instance is *running* | Stop it when not testing; terminate when the project ends |
| EBS volume (GB-month) | Volume exists, even if instance stopped | Terminate the instance / delete leftover volumes |
| Public IPv4 address / Elastic IP | Address is allocated | Release Elastic IPs you no longer use |
| Data transfer out | Traffic leaves AWS | Keep load tests short; run Locust in bursts |
| EBS snapshots | Snapshot exists | Delete old snapshots |

Recommendations:

* Create an **AWS Budget** (Billing -> Budgets) with an email alert at a small amount.
* Stop the instance after every work session; terminate it after the final demo.
* Use one small instance; this project does not need load balancers, RDS or NAT gateways.
* Check the **Billing dashboard** and the *EC2 -> Instances / Volumes / Elastic IPs* pages
  across all regions before you finish.

## Troubleshooting

| Problem | Fix |
|---|---|
| Browser times out | Security group missing port 80 rule, or wrong (old) public IP after a stop/start |
| `permission denied ... docker.sock` | Log out and in again after `ec2-setup.sh` (docker group) |
| Build killed / very slow on `*.micro` | Confirm swap: `swapon --show`; or use a `*.small` instance |
| `502 Bad Gateway` | Backend not healthy yet: `docker compose ps`, `docker compose logs backend` |
| SSH `Connection timed out` | Your IP changed; update the SSH rule to "My IP" |
| `UNPROTECTED PRIVATE KEY FILE` | `chmod 400 ~/.ssh/cloudpulse-key.pem` |

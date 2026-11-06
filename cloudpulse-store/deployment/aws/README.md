# `deployment/aws/` — EC2 scripts and host configuration

Scripts that run **on an AWS EC2 Ubuntu instance**. They never create AWS resources, never
read AWS credentials and never spend money; you create, stop and terminate the instance yourself.

| File | Run | What it does |
|---|---|---|
| `ec2-setup.sh` | Once, as the `ubuntu` user | Updates packages, installs Docker Engine + Compose plugin from Docker's official apt repository, adds the user to the `docker` group, configures container log rotation (10 MB × 3), creates a 2 GB swap file when RAM < 2 GB |
| `deploy.sh` | Every deploy/update | `git pull --ff-only` (only if `.git` exists inside `cloudpulse-store/`), creates `.env` from `.env.example` if missing (sets `ENVIRONMENT=production`, random Grafana password, `chmod 600`), `docker compose up --build -d`, waits up to 60 s for `/api/ready`, prints the public URLs from the instance metadata service (IMDSv2). Options: `--no-pull`, `--monitoring` |
| `nginx-site.conf` | Optional, host Nginx | HTTPS reverse proxy (Let's Encrypt) in front of the container bound to `127.0.0.1:8080`; replace `store.example.com` with your domain |

```bash
# on the instance, inside the cloned repository
cd ~/cloudpulse/cloudpulse-store
bash deployment/aws/ec2-setup.sh          # then log out and back in
git -C .. pull --ff-only                  # monorepo: pull at the repository root
bash deployment/aws/deploy.sh             # add --monitoring for Prometheus + Grafana
```

Security: open SSH (22) to your own IP only and HTTP/HTTPS (80/443) publicly. Never open 8000,
9090 or 3000; Prometheus and Grafana bind to `127.0.0.1` and are reached through an SSH tunnel.
Keep the `.pem` key outside the repository.

Overview: [`../README.md`](../README.md) · Full guide: [`../../docs/AWS_DEPLOYMENT.md`](../../docs/AWS_DEPLOYMENT.md)

# Deployment

Files used to run CloudPulse Store on an **AWS EC2 Ubuntu** instance.
The full step-by-step guide (instance creation, security groups, HTTPS, costs) is in
[`../docs/AWS_DEPLOYMENT.md`](../docs/AWS_DEPLOYMENT.md).

| File | Run where | What it does |
|---|---|---|
| `aws/ec2-setup.sh` | On the EC2 instance, once | Installs Docker Engine + Compose plugin, enables log rotation, adds swap on small instances |
| `aws/deploy.sh` | On the EC2 instance, every deploy/update | Pulls code (git), creates `.env` if missing, `docker compose up --build -d`, waits for `/api/ready`, prints URLs |
| `aws/nginx-site.conf` | Host Nginx, optional | Reverse proxy for HTTPS with a domain + Let's Encrypt certificate |

These scripts **never create AWS resources** and never spend money. You create the
EC2 instance yourself in the AWS console and stop/terminate it yourself.

## Quick version

```bash
# On your Mac
ssh -i ~/.ssh/cloudpulse-key.pem ubuntu@<EC2-public-IP>

# On the instance
git clone <your-repository-url> cloudpulse          # or copy with scp/rsync
cd cloudpulse/cloudpulse-store
bash deployment/aws/ec2-setup.sh
exit                                                 # log out so the docker group applies

ssh -i ~/.ssh/cloudpulse-key.pem ubuntu@<EC2-public-IP>
cd cloudpulse/cloudpulse-store
bash deployment/aws/deploy.sh                        # use --no-pull if you copied files
```

`deploy.sh` runs `git pull` only when `.git` is inside `cloudpulse-store/`. In the `cloudpulse`
monorepo the `.git` folder is at the repository root, so update the code first with
`git -C .. pull --ff-only`, then run `deploy.sh`.

Then open `http://<EC2-public-IP>/`.

## Ports

| Port | Open to | Why |
|---|---|---|
| 22 (SSH) | **Your IP only** (`x.x.x.x/32`) | Administration |
| 80 (HTTP) | `0.0.0.0/0` | Website + API + monitoring endpoints |
| 443 (HTTPS) | `0.0.0.0/0` | Only if you enable HTTPS |

Never open 8000 (backend), 9090 (Prometheus) or 3000 (Grafana). The backend is
not published at all, and Prometheus/Grafana bind to `127.0.0.1` only; reach them
with an SSH tunnel:

```bash
ssh -i ~/.ssh/cloudpulse-key.pem -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 ubuntu@<EC2-public-IP>
```

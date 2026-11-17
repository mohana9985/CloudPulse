# Two-EC2 deployment: store on one instance, dashboard on the other

You create, start, stop and terminate both instances yourself in the AWS console. The scripts
create no AWS resources. Check the [EC2 pricing page](https://aws.amazon.com/ec2/pricing/on-demand/)
for your region: two instances cost twice as much as one, so **stop both** after every session.

```
                Internet
   :80 (everyone)  |        :8501 (your IP only)
        v          |               v
+-------------------------+   +------------------------------+
| EC2 #1  cloudpulse-store|   | EC2 #2  cloudpulse-dashboard |
|  Nginx frontend :80     |   |  Streamlit dashboard :8501   |
|  gateway :8090  <-------+---+- Website workload page       |
|  loadgen :8095  <-------+---+- (drives the website)        |
|  Prometheus :9090 <-----+---+- CPU/memory charts           |
|   └─ scrapes ───────────+---+> coordinator :8100           |
|  backend-1/2/3          |   |  worker-1/2/3                |
|  Grafana 127.0.0.1:3000 |   |                              |
+-------------------------+   +------------------------------+
        same VPC, traffic over PRIVATE IPs (172.31.x.x)
```

Ports 8090 / 8095 / 9090 / 8100 have **no authentication** (algorithm switch, crash buttons), so
they are opened only between the two instances, never to the internet. Private IPs do not change
when you stop/start an instance; public IPs do (unless you pay for an Elastic IP).

## 0. Before you start: push the code to GitHub

Both instances are created fresh and get the code **only** with `git clone` from
`https://github.com/mohana9985/CloudPulse` (public). Whatever is not pushed does not exist on EC2,
so commit and push first. `.env` files are never pushed (`.gitignore`); you create them on each instance.

## 1. Launch the instances

EC2 -> Launch instance, twice (both new). Same settings for both except the name:

| Setting | EC2 #1 | EC2 #2 |
|---|---|---|
| Name | `cloudpulse-store` | `cloudpulse-dashboard` |
| AMI | Ubuntu Server 24.04 LTS | same |
| Type | `t4g.small` (2 GB) | `t4g.small` (or `t4g.micro` 1 GB; setup script adds swap, image build is slower) |
| Key pair | `cloudpulse-key` (still in EC2 -> Key pairs after deleting the instance; if you no longer have the `.pem` file, create a new key pair) | same key |
| Network | default VPC, **same subnet / AZ** as #1, auto-assign public IP | same |
| Storage | 20 GiB gp3 | 20 GiB gp3 |

Same AZ keeps traffic between them free and low-latency.

## 2. Security groups

Create two security groups (EC2 -> Security Groups). Using the *other group* as the source
(not an IP) means the rules keep working after stop/start.

**`sg-cloudpulse-store`** (attach to EC2 #1)

| Type | Port | Source |
|---|---|---|
| SSH | 22 | My IP |
| HTTP | 80 | 0.0.0.0/0 |
| Custom TCP | 8090 | `sg-cloudpulse-dashboard` |
| Custom TCP | 8095 | `sg-cloudpulse-dashboard` |
| Custom TCP | 9090 | `sg-cloudpulse-dashboard` |

**`sg-cloudpulse-dashboard`** (attach to EC2 #2)

| Type | Port | Source |
|---|---|---|
| SSH | 22 | My IP |
| Custom TCP | 8501 | My IP |
| Custom TCP | 8100 | `sg-cloudpulse-store` |

Create both groups first with SSH only, then add the cross-references (each needs the other to exist).
Select the groups in the launch wizard ("Select existing security group"), or later: Actions -> Security -> Change security groups.

If your home IP changes, edit the two "My IP" rules.

## 3. Note the private IPs

EC2 -> Instances -> select each -> **Private IPv4 address**. Below:
`STORE_PRIV` = EC2 #1, `DASH_PRIV` = EC2 #2.

## 4. Configuration rule: everything machine-specific is in `.env`

Both instances clone the **same GitHub repository**. Nothing machine-specific is committed:
IPs, passwords, binds and the two-EC2 switch live only in `.env` files, which are in `.gitignore`.
Committed templates (no secrets): `cloudpulse-store/.env.example`, `cloudpulse-scheduler/.env.example`.

| Instance | `.env` file it uses | Two-EC2 lines to uncomment |
|---|---|---|
| EC2 #1 store | `cloudpulse-store/.env` | `COMPOSE_FILE`, `SCHEDULER_HOST=<DASH_PRIV>`, `GATEWAY_BIND`, `LOADGEN_BIND`, `PROMETHEUS_BIND`, and `COMPOSE_PROFILES=monitoring` |
| EC2 #2 dashboard | `cloudpulse-scheduler/.env` | `COMPOSE_FILE`, `STORE_HOST=<STORE_PRIV>`, `DASHBOARD_BIND`, `COORDINATOR_BIND` |

The deploy scripts take no IPs or passwords as arguments; they read `.env`. Plain `docker compose ...`
commands also read it (`COMPOSE_FILE`, `COMPOSE_PROFILES`), so manual restarts keep the same setup.
Updating = `git pull` (the scripts do it) — `.env` is untouched by pulls.

The repository must be reachable from the instances: public repo -> `git clone https://github.com/<user>/CloudPulse.git`.
Private repo -> add a read-only **deploy key** on each instance (`ssh-keygen -t ed25519`, paste the
`.pub` into GitHub -> repo Settings -> Deploy keys) and clone with the `git@github.com:` URL.
Never put a GitHub token in a committed file.

## 4b. Your computer: macOS or Windows

Only SSH runs on your computer; every command after `ssh` runs on Ubuntu and is the same for
everyone. macOS/Linux: `chmod 400 ~/.ssh/cloudpulse-key.pem` once, then the `ssh -i ~/.ssh/...`
lines below. Windows 10/11 (PowerShell, OpenSSH is built in):

```powershell
# Windows (PowerShell): put the key in your user's .ssh folder and make it private (once)
New-Item -ItemType Directory -Force $HOME\.ssh | Out-Null
Move-Item $HOME\Downloads\cloudpulse-key.pem $HOME\.ssh\
icacls $HOME\.ssh\cloudpulse-key.pem /inheritance:r /grant:r "$($env:USERNAME):R"
ssh -i $HOME\.ssh\cloudpulse-key.pem ubuntu@<EC2-1-public-IP>
```

In every `ssh` line of this guide write `-i $HOME\.ssh\cloudpulse-key.pem` instead of
`-i ~/.ssh/cloudpulse-key.pem`; open URLs with `Start-Process http://...` or the browser.

## 5. EC2 #1: the store

```bash
ssh -i ~/.ssh/cloudpulse-key.pem ubuntu@<EC2-1-public-IP>
git clone https://github.com/mohana9985/CloudPulse.git cloudpulse                  # first time only
cd cloudpulse/cloudpulse-store
bash deployment/aws/ec2-setup.sh                 # first time only, then log out and in again

cd ~/cloudpulse/cloudpulse-store
cp .env.example .env && chmod 600 .env           # first time only
nano .env       # ENVIRONMENT=production, uncomment the Two-EC2 block + COMPOSE_PROFILES=monitoring,
                # set SCHEDULER_HOST=<DASH_PRIV>. Leave GRAFANA_ADMIN_PASSWORD as is: deploy.sh
                # replaces the placeholder with a random password, stored in .env.
bash deployment/aws/deploy.sh                    # git pull + build + start
```

`deploy.sh` stops with an error if two-EC2 mode is on but `SCHEDULER_HOST` is still the placeholder.
Check: `http://<EC2-1-public-IP>/` shows the shop.

## 5b. EC2 #2: the dashboard + scheduler cluster

```bash
ssh -i ~/.ssh/cloudpulse-key.pem ubuntu@<EC2-2-public-IP>
git clone https://github.com/mohana9985/CloudPulse.git cloudpulse                  # first time only
cd cloudpulse/cloudpulse-store && bash deployment/aws/ec2-setup.sh   # Docker; log out and in again

cd ~/cloudpulse/cloudpulse-scheduler
cp .env.example .env && chmod 600 .env           # first time only
nano .env       # uncomment the Two-EC2 block, set STORE_HOST=<STORE_PRIV>
bash deployment/ec2-deploy-live.sh               # git pull + build + start (dashboard included)
```

The script first checks it can reach the store's gateway, loadgen and Prometheus. A `FAIL` line
means the store's `.env` Two-EC2 block is not enabled, or the security group rules of step 2 are missing.

## 6. Use it

| What | URL |
|---|---|
| Store website | `http://<EC2-1-public-IP>/` |
| Dashboard (Website workload + Compute cluster) | `http://<EC2-2-public-IP>:8501` |
| Grafana | `bash deployment/aws/tunnel.sh` (Windows: `powershell -ExecutionPolicy Bypass -File deployment\aws\tunnel.ps1`) on your computer, then `http://localhost:3001` (password: `GRAFANA_ADMIN_PASSWORD` in EC2 #1 `.env`) |

The dashboard's Grafana links point to `http://localhost:3001`, so they work while the tunnel is open. AWS uses port 3001 so it never clashes with a local Grafana on `http://localhost:3000`. The tunnel script reads the IPs, key and local ports from the `AWS_*` lines of `cloudpulse-store/.env` on your computer and also opens Prometheus `9091`, gateway `8091`, loadgen `8096` and coordinator `8101`; full table in [`../deployment/aws/README.md`](../deployment/aws/README.md#port-map-local-docker-vs-aws).

**No terminal during a demo:** on EC2 #1 set `GRAFANA_BIND=0.0.0.0` and `GRAFANA_PORT=3001` in `.env`, run `docker compose up -d grafana`, and add a security group inbound rule TCP 3001 from **My IP** only. Grafana is then at `http://<EC2-1-public-IP>:3001` with no tunnel. On EC2 #2 set `GRAFANA_PUBLIC_URL=http://<EC2-1-public-IP>:3001` in `.env` and run `docker compose up -d dashboard` so the Streamlit links match.

Prometheus on EC2 #1 scrapes the coordinator on EC2 #2 (`cloudpulse-coordinator` resolves to
`SCHEDULER_HOST` through `extra_hosts`). Check from EC2 #1:
`curl -s localhost:9090/api/v1/targets | grep -o '"health":"[a-z]*"'` -> all `up`.

## 7. Stop / restart

Stop both instances in the console after each session (containers have `restart: unless-stopped`
and come back on start). Public IPs change on start; private IPs and security group rules do not,
so nothing needs redeploying.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Dashboard: "Website stack unreachable" | On EC2 #2: `curl http://<STORE_PRIV>:8090/gateway/health`. Timeout = SG rule missing; refused = store `.env` Two-EC2 block not enabled |
| Dashboard has no CPU/memory charts | `COMPOSE_PROFILES=monitoring` not set in the store `.env` |
| Coordinator target `down` in Prometheus | SG rule 8100 from `sg-cloudpulse-store` missing, or wrong `SCHEDULER_HOST` in EC2 #1 `.env` |
| Cannot open :8501 | "My IP" changed; update the SG rule |
| Back to single instance | Comment out the Two-EC2 block in both `.env` files and redeploy |

Verified locally (Mac, Colima) by running the dashboard on its own Docker network with only
`STORE_HOST` pointing at the store's published ports: gateway, loadgen and Prometheus reachable,
coordinator scraped `up`. Not yet run on real EC2.

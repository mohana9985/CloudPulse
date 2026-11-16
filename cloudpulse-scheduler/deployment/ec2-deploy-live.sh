#!/usr/bin/env bash
# Deploy the CloudPulse live scheduler cluster on the EXISTING EC2 instance (t4g.small, 2 GB),
# next to the CloudPulse Store. Creates no AWS resources. Run on the instance from
# cloudpulse-scheduler/:   bash deployment/ec2-deploy-live.sh [--with-dashboard] [--with-monitoring]
#
#   --no-pull   skip "git pull" (default: pull the latest code from GitHub first)
#
# All settings (store IP, binds, CPU quotas) live in cloudpulse-scheduler/.env (from .env.example),
# never in flags or committed files. Two-EC2 setup (../cloudpulse-store/docs/AWS_TWO_EC2.md):
# uncomment the "Two-EC2 setup" block in .env on the dashboard instance; the script then starts
# coordinator + workers + dashboard and talks to the store over the VPC private network.
set -euo pipefail
cd "$(dirname "$0")/.."

WITH_DASH=false; WITH_MON=false; PULL=true
for a in "$@"; do
  case "$a" in
    --with-dashboard) WITH_DASH=true ;;
    --with-monitoring) WITH_MON=true ;;
    --no-pull) PULL=false ;;
    *) echo "unknown option $a"; exit 2 ;;
  esac
done

if $PULL && git rev-parse --git-dir >/dev/null 2>&1; then
  echo "Pulling latest code from GitHub ..."
  git -C "$(git rev-parse --show-toplevel)" pull --ff-only
fi

if [ ! -f .env ]; then
  cp .env.example .env && chmod 600 .env
  echo "Created .env from .env.example. Review it (nano .env); for two EC2s uncomment the Two-EC2 block."
fi

# Two-EC2 mode: COMPOSE_FILE in .env includes compose.two-host.yaml, STORE_HOST = store private IP.
STORE_HOST=""
if grep -qE '^COMPOSE_FILE=.*compose\.two-host\.yaml' .env; then
  STORE_HOST=$(grep -E '^STORE_HOST=' .env | cut -d= -f2- || true)
  if [ -z "$STORE_HOST" ] || [ "${STORE_HOST#<}" != "$STORE_HOST" ]; then
    echo "Two-EC2 mode is on but STORE_HOST in .env is not set to the store EC2 private IP"; exit 1
  fi
  WITH_DASH=true
fi

# Memory guard: coordinator 192M + 3 x 128M workers (+ 320M dashboard) are LIMITS;
# measured use is ~40 MB per service. Require headroom before starting.
need_mb=350; $WITH_DASH && need_mb=$((need_mb + 200))
avail_mb=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
echo "MemAvailable: ${avail_mb} MB (need >= ${need_mb} MB)"
if [ "$avail_mb" -lt "$need_mb" ]; then
  echo "Not enough free memory. Stop something first (e.g. the store's monitoring profile) or add swap."
  exit 1
fi

# CPU quotas sum to 1.5 of the 2 vCPUs, leaving room for the store and the coordinator.
# The dashboard's "Website workload" page needs the store network (gateway, loadgen, Prometheus),
# so --with-dashboard also applies compose.monitoring.yaml.
files=(-f compose.yaml)
if [ -n "$STORE_HOST" ]; then
  files=(-f compose.yaml -f compose.two-host.yaml)
  echo "Checking the store at ${STORE_HOST} (gateway 8090, loadgen 8095, Prometheus 9090) ..."
  for p in 8090/gateway/health 8095/loadgen/health 9090/-/ready; do
    curl -sf -m 3 "http://${STORE_HOST}:${p}" >/dev/null && echo "  ok   :${p%%/*}" \
      || echo "  FAIL :${p%%/*}  (store .env Two-EC2 block not enabled, or security group blocks it)"
  done
elif $WITH_MON || $WITH_DASH; then
  docker network inspect cloudpulse-store_cloudpulse >/dev/null 2>&1 \
    || { echo "Store network not found: start the store first"; exit 1; }
  files+=(-f compose.monitoring.yaml)
fi
services=(coordinator worker-1 worker-2 worker-3)
$WITH_DASH && services+=(dashboard)

docker compose "${files[@]}" build "${services[@]}"
docker compose "${files[@]}" up -d "${services[@]}"

echo "Waiting for 3 active workers ..."
for _ in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8100/health | grep -q '"active_workers":3'; then
    curl -s http://127.0.0.1:8100/health; echo
    docker stats --no-stream --format '{{.Name}} {{.MemUsage}}'
    free -m
    if [ -n "$STORE_HOST" ]; then
      echo "OK. Dashboard: http://<this-EC2-public-IP>:8501  (security group: port 8501 from your IP only)"
      echo "    Grafana:   ssh -i <key>.pem -N -L 3000:127.0.0.1:3000 ubuntu@<store-EC2-public-IP>, then http://localhost:3000"
      exit 0
    fi
    echo "OK. From your Mac: ssh -i <key>.pem -N -L 8100:127.0.0.1:8100 -L 8501:127.0.0.1:8501 -L 3000:127.0.0.1:3000 ubuntu@<EC2-IP>"
    exit 0
  fi
  sleep 2
done
echo "Cluster did not become healthy; see: docker compose logs --tail 50"; exit 1

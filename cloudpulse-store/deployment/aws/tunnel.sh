#!/usr/bin/env bash
# Open SSH tunnels from YOUR COMPUTER (macOS / Linux) to the AWS instances.
# Windows PowerShell: deployment/aws/tunnel.ps1
#
# Local Docker keeps the normal ports (Grafana 3000, Prometheus 9090, gateway 8090, loadgen 8095,
# coordinator 8100). AWS is opened on DIFFERENT local ports taken from .env, so the local stack and
# the AWS tunnel never clash:
#   AWS_GRAFANA_LOCAL_PORT     (3001) -> store EC2     127.0.0.1:3000
#   AWS_PROMETHEUS_LOCAL_PORT  (9091) -> store EC2     127.0.0.1:9090
#   AWS_GATEWAY_LOCAL_PORT     (8091) -> store EC2     127.0.0.1:8090
#   AWS_LOADGEN_LOCAL_PORT     (8096) -> store EC2     127.0.0.1:8095
#   AWS_COORDINATOR_LOCAL_PORT (8101) -> dashboard EC2 127.0.0.1:8100 (only if AWS_SCHEDULER_PUBLIC_IP is set)
# IPs, key path, user and ports all come from cloudpulse-store/.env (never from flags).
#
# Usage (from cloudpulse-store/):  bash deployment/aws/tunnel.sh      Ctrl+C closes the tunnels.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found (cp .env.example .env, then fill the AWS_* lines)" >&2
  exit 1
fi

# Read KEY from .env (last value wins); fall back to a default.
env_get() {
  local v
  v=$(grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true)
  v="${v%\"}"; v="${v#\"}"
  echo "${v:-$2}"
}
is_set() { [[ -n "$1" && "$1" != \<* ]]; }

KEY=$(env_get AWS_SSH_KEY "$HOME/.ssh/cloudpulse-key.pem")
KEY="${KEY/#\~/$HOME}"
USER_NAME=$(env_get AWS_SSH_USER ubuntu)
STORE_IP=$(env_get AWS_STORE_PUBLIC_IP "")
SCHED_IP=$(env_get AWS_SCHEDULER_PUBLIC_IP "")
GRAFANA=$(env_get AWS_GRAFANA_LOCAL_PORT 3001)
PROM=$(env_get AWS_PROMETHEUS_LOCAL_PORT 9091)
GATEWAY=$(env_get AWS_GATEWAY_LOCAL_PORT 8091)
LOADGEN=$(env_get AWS_LOADGEN_LOCAL_PORT 8096)
COORD=$(env_get AWS_COORDINATOR_LOCAL_PORT 8101)

if ! is_set "$STORE_IP"; then
  echo "ERROR: set AWS_STORE_PUBLIC_IP in $ENV_FILE" >&2
  exit 1
fi
[[ -f "$KEY" ]] || { echo "ERROR: SSH key not found: $KEY (AWS_SSH_KEY in .env)" >&2; exit 1; }

SSH_OPTS=(-i "$KEY" -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30)
PIDS=()
cleanup() { kill "${PIDS[@]}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

ssh "${SSH_OPTS[@]}" \
  -L "$GRAFANA:127.0.0.1:3000" -L "$PROM:127.0.0.1:9090" \
  -L "$GATEWAY:127.0.0.1:8090" -L "$LOADGEN:127.0.0.1:8095" \
  "$USER_NAME@$STORE_IP" &
PIDS+=($!)
echo "==> Store EC2 ($STORE_IP)"
echo "    Grafana     http://localhost:$GRAFANA"
echo "    Prometheus  http://localhost:$PROM"
echo "    Gateway     http://localhost:$GATEWAY/gateway/health"
echo "    Loadgen     http://localhost:$LOADGEN/loadgen/health"

if is_set "$SCHED_IP"; then
  ssh "${SSH_OPTS[@]}" -L "$COORD:127.0.0.1:8100" "$USER_NAME@$SCHED_IP" &
  PIDS+=($!)
  echo "==> Dashboard EC2 ($SCHED_IP)"
  echo "    Coordinator http://localhost:$COORD/health"
fi
echo "Tunnels open. Ctrl+C to close."
wait

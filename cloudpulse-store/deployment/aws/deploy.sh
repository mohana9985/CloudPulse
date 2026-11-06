#!/usr/bin/env bash
# Build and (re)start CloudPulse Store with Docker Compose on the EC2 instance.
# Usage (from anywhere inside the project on the server):
#   bash deployment/aws/deploy.sh            # pull latest code (if git) + rebuild + restart
#   bash deployment/aws/deploy.sh --no-pull  # rebuild what is on disk (e.g. copied with scp/rsync)
#   bash deployment/aws/deploy.sh --monitoring   # also start Prometheus + Grafana (localhost only)
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_DIR"

PULL=true
PROFILE_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --no-pull) PULL=false ;;
    --monitoring) PROFILE_ARGS=(--profile monitoring) ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

if [[ "$PULL" == true && -d .git ]]; then
  echo "==> Pulling latest code"
  git pull --ff-only
fi

if [[ ! -f .env ]]; then
  echo "==> No .env found: creating one from .env.example (ENVIRONMENT=production)"
  cp .env.example .env
  sed -i 's/^ENVIRONMENT=.*/ENVIRONMENT=production/' .env
  # Random Grafana password so the example value is never used on a server.
  sed -i "s/^GRAFANA_ADMIN_PASSWORD=.*/GRAFANA_ADMIN_PASSWORD=$(openssl rand -hex 16)/" .env
  chmod 600 .env
  echo "    Review it with: nano .env"
fi

echo "==> Building images and starting containers"
docker compose "${PROFILE_ARGS[@]}" up --build -d --remove-orphans

echo "==> Waiting for the site to become healthy"
PORT=$(grep -E '^HTTP_PORT=' .env | cut -d= -f2 || true)
PORT=${PORT:-80}
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PORT}/api/ready" > /dev/null 2>&1; then
    echo "    Healthy after $((i * 2))s"
    break
  fi
  if [[ $i -eq 30 ]]; then
    echo "ERROR: site not healthy after 60s. Check: docker compose logs --tail 100" >&2
    docker compose ps
    exit 1
  fi
  sleep 2
done

docker compose ps
docker image prune -f > /dev/null

# Public IP from the EC2 instance metadata service (IMDSv2).
TOKEN=$(curl -fsS -m 2 -X PUT http://169.254.169.254/latest/api/token \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null || true)
PUBLIC_IP=$(curl -fsS -m 2 -H "X-aws-ec2-metadata-token: ${TOKEN}" \
  http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "<EC2-public-IP>")

echo
echo "CloudPulse Store is running:"
echo "  Website : http://${PUBLIC_IP}/"
echo "  API docs: http://${PUBLIC_IP}/api/docs"
echo "  Health  : http://${PUBLIC_IP}/api/health"
echo "  Metrics : http://${PUBLIC_IP}/api/metrics"

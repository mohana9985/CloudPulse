#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu (22.04 / 24.04) AWS EC2 instance for CloudPulse Store.
# This script creates NO AWS resources and costs nothing by itself.
# Usage (on the EC2 instance):   bash deployment/aws/ec2-setup.sh
set -euo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Run as the normal 'ubuntu' user (the script uses sudo where needed)." >&2
  exit 1
fi

. /etc/os-release
if [[ "${ID}" != "ubuntu" ]]; then
  echo "This script supports Ubuntu only (found: ${ID})." >&2
  exit 1
fi

echo "==> Updating packages"
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl git

echo "==> Installing Docker Engine (official repository)"
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME:-$VERSION_CODENAME} stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

# Rotate container logs so a long load test cannot fill the disk.
if [[ ! -f /etc/docker/daemon.json ]]; then
  echo "==> Configuring Docker log rotation"
  echo '{ "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "3" } }' \
    | sudo tee /etc/docker/daemon.json > /dev/null
  sudo systemctl restart docker
fi

# Swap for instances with less than 2 GB RAM (e.g. t3.micro / t4g.micro / t3.small).
MEM_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
if [[ "${MEM_MB}" -lt 2048 ]] && ! swapon --show | grep -q /swapfile; then
  echo "==> ${MEM_MB} MB RAM detected: creating 2 GB swap file"
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab > /dev/null
fi

echo
docker --version || true
sudo docker compose version
echo
echo "Setup complete. Log out and SSH in again so the 'docker' group applies,"
echo "then run:  cd cloudpulse-store && bash deployment/aws/deploy.sh"

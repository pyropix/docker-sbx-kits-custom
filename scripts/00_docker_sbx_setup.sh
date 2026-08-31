#!/usr/bin/env bash
# Convenience wrapper around sbx_setup.py.
# Prefer: uv run sbx_setup.py
set -euo pipefail

## Telemetry: opt out of all analytics
export SBX_NO_TELEMETRY=1

curl -fsSL https://get.docker.com | sudo REPO_ONLY=1 sh
sudo apt-get install -y docker-sbx
sudo usermod -aG kvm "$USER"

# newgrp kvm cannot work from a subprocess — it spawns a replacement shell
# that exits immediately, leaving this process's groups unchanged. Log out
# and back in (or reboot) before running sbx.
echo ""
echo "kvm group membership takes effect in new login sessions."
echo "Log out and log back in (or reboot) before running sbx."

# Login to sbx
sbx login

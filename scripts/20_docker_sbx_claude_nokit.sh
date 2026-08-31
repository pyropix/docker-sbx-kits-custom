#!/usr/bin/env bash
# Convenience wrapper for running Claude Code without a kit.
# Prefer: ./sbx_run.py --no-kit
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Starting Claude sandbox (no kit) at $REPO_ROOT..."

# Run with access to local workspace
sbx run --name claude-nokit claude "$REPO_ROOT"

read -r -p "Delete sandbox claude-nokit? [y/N] " answer
if [[ "${answer,,}" =~ ^y ]]; then
  sbx stop claude-nokit
  sbx rm claude-nokit --force
fi

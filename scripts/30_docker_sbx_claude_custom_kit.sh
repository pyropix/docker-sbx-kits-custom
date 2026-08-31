#!/usr/bin/env bash
# Convenience wrapper for running Claude Code with the custom kit.
# Prefer: ./sbx_run.py
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Starting Claude sandbox (custom kit) at $REPO_ROOT..."

# Run with access to local workspace
sbx run --name claude-custom-kit --kit "$REPO_ROOT/sbx-kits/claude-custom/" claude "$REPO_ROOT"

read -r -p "Delete sandbox claude-custom-kit? [y/N] " answer
if [[ "${answer,,}" =~ ^y ]]; then
  sbx stop claude-custom-kit
  sbx rm claude-custom-kit --force
fi

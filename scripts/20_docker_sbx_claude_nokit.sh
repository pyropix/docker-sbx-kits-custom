#!/usr/bin/env bash
set -euxo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Run with access to local workspace
sbx run --name claude-nokit claude "$REPO_ROOT"

read -r -p "Delete sandbox claude-nokit? [y/N] " answer
if [[ "${answer,,}" =~ ^y ]]; then
  sbx stop claude-nokit
  sbx rm claude-nokit --force
fi
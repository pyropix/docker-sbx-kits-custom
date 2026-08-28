#!/usr/bin/env bash
set -euxo pipefail

# Run with access to local workspace
sbx run --name claude-nokit claude "$(pwd)"

read -r -p "Delete sandbox claude-nokit? [y/N] " answer
if [[ "${answer,,}" =~ ^y ]]; then
  sbx stop claude-nokit
  sbx rm claude-nokit --force
fi
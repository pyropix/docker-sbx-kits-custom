#!/usr/bin/env bash
set -euxo pipefail

# Run with access to local workspace
sbx run --name claude-custom-kit --kit ./sbx-kits/claude-custom/ claude "$(pwd)"

read -r -p "Delete sandbox claude-custom-kit? [y/N] " answer
if [[ "${answer,,}" =~ ^y ]]; then
  sbx stop claude-custom-kit
  sbx rm claude-custom-kit --force
fi
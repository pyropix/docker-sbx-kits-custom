#!/usr/bin/env bash
# Convenience wrapper for re-attaching to the custom-kit sandbox in bash mode.
# Prefer: ./sbx_run.py --mode bash
set -euo pipefail

echo "Attaching to claude-custom-kit sandbox in bash mode..."

# Re-attach to the running custom-kit sandbox (created by 30_docker_sbx_claude_custom_kit.sh)
sbx exec -it claude-custom-kit bash

#!/usr/bin/env bash
# Convenience wrapper for running Claude Code with the Microsoft Learn MCP.
# Prefer: ./sbx_run.py --no-kit --mcp mslearn
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Registering mslearn MCP server..."

# Create a new sandbox with the current working directory mounted
sbx mcp add mslearn --url https://learn.microsoft.com/api/mcp

# List available MCPs
sbx mcp ls

echo "Starting Claude sandbox with MCP at $REPO_ROOT..."

# Run a sandbox with the Microsoft Learn MCP
sbx run claude --name claude-mcp --static-mcp mslearn "$REPO_ROOT"

read -r -p "Delete sandbox claude-mcp? [y/N] " answer
if [[ "${answer,,}" =~ ^y ]]; then
  sbx stop claude-mcp
  sbx rm claude-mcp --force
fi

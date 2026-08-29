#!/usr/bin/env bash
set -euxo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Create a new sandbox with the current working directory mounted
sbx mcp add mslearn --url https://learn.microsoft.com/api/mcp

# List available MCPs
sbx mcp ls

# Run a sandbox with the Microsoft Learn MCP
sbx run claude --name claude-mcp --static-mcp mslearn "$REPO_ROOT"

read -r -p "Delete sandbox claude-mcp? [y/N] " answer
if [[ "${answer,,}" =~ ^y ]]; then
  sbx stop claude-mcp
  sbx rm claude-mcp --force
fi
#!/usr/bin/env bash
# Convenience wrapper for SSH access to the no-kit sandbox.
# Prefer: ./sbx_run.py --no-kit --mode ssh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Create a new sandbox with the current working directory mounted (skip if it already exists)
if create_output=$(sbx create --name claude-ssh claude "$REPO_ROOT" 2>&1); then
  echo "$create_output"
elif grep -q "already exists" <<<"$create_output"; then
  echo "$create_output"
  echo "Sandbox already exists, skipping creation."
else
  echo "$create_output" >&2
  exit 1
fi

# Setup SSH access to the sandbox
sbx setup ssh --alias claude-ssh.sbx

# Resolve the workspace path inside the sandbox (may differ from the host path).
# SC2016: single quotes are intentional — $WORKSPACE_DIR is expanded by the sandbox shell.
# shellcheck disable=SC2016
sandbox_path=$(sbx exec claude-ssh sh -c 'echo "$WORKSPACE_DIR"' 2>/dev/null | tail -1)
[ -z "$sandbox_path" ] && sandbox_path="$REPO_ROOT"

echo "Connecting via SSH to $sandbox_path..."

# Run SSH into the sandbox
ssh -t claude-ssh.sbx "cd $(printf '%q' "$sandbox_path") ; bash --login"

## Note: You have to manually stop the container when you are done with it.
## Otherwise it will keep running in the background. You can do this by running:
# sbx stop claude-ssh
# sbx rm claude-ssh --force

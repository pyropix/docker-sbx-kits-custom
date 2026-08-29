#!/usr/bin/env bash
set -euxo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Create a new sandbox with the current working directory mounted (skip if it already exists)
if create_output=$(sbx create --name claude-custom-ssh-vscode --kit "$REPO_ROOT/sbx-kits/claude-custom/" claude "$REPO_ROOT" 2>&1); then
  echo "$create_output"
elif grep -q "already exists" <<<"$create_output"; then
  echo "$create_output"
  echo "Sandbox already exists, skipping creation."
else
  echo "$create_output" >&2
  exit 1
fi

# Setup SSH access to the sandbox
sbx setup ssh --alias claude-custom-ssh-vscode.sbx

# Run VS Code with remote SSH connection to the sandbox
## Note: you have to install the "Remote - SSH" extension in VS Code for this to work.
code --remote ssh-remote+claude-custom-ssh-vscode.sbx "$REPO_ROOT"

## Note: You have to manually stop the container when you are done with it.
## Otherwise it will keep running in the background. You can do this by running:
# sbx stop claude-custom-ssh-vscode
# sbx rm claude-custom-ssh-vscode --force
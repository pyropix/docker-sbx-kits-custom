#!/usr/bin/env bash
set -euxo pipefail

# Create a new sandbox with the current working directory mounted (skip if it already exists)
create_output=$(sbx create --name claude-ssh-vscode claude "$(pwd)" 2>&1) && echo "$create_output" || {
  if grep -q "already exists" <<<"$create_output"; then
    echo "$create_output"
    echo "Sandbox already exists, skipping creation."
  else
    echo "$create_output" >&2
    exit 1
  fi
}

# Setup SSH access to the sandbox
sbx setup ssh --alias claude-ssh-vscode.sbx

# Run VS Code with remote SSH connection to the sandbox
## Note: you have to install the "Remote - SSH" extension in VS Code for this to work.
code --remote ssh-remote+claude-ssh-vscode.sbx "$(pwd)"

## Note: You have to manually stop the container when you are done with it.
## Otherwise it will keep running in the background. You can do this by running:
# sbx stop claude-ssh-vscode
# sbx rm claude-ssh-vscode --force
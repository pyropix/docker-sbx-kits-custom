#!/usr/bin/env bash
set -euxo pipefail

# Create a new sandbox with the current working directory mounted
sbx create --name claude-ssh-vscode claude "$(pwd)"

# Setup SSH access to the sandbox
sbx setup ssh --alias claude-ssh-vscode.sbx

# Run VS Code with remote SSH connection to the sandbox
## Note: you have to install the "Remote - SSH" extension in VS Code for this to work.
code --remote ssh-remote+claude-ssh-vscode.sbx "$(pwd)"

read -r -p "Delete sandbox claude-ssh-vscode? [y/N] " answer
if [[ "${answer,,}" =~ ^y ]]; then
  sbx stop claude-ssh-vscode
  sbx rm claude-ssh-vscode --force
fi
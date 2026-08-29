#!/usr/bin/env bash
set -euxo pipefail

# Create a new sandbox with the current working directory mounted (skip if it already exists)
create_output=$(sbx create --name claude-custom-ssh --kit ./sbx-kits/claude-custom/ claude "$(pwd)" 2>&1) && echo "$create_output" || {
  if grep -q "already exists" <<<"$create_output"; then
    echo "$create_output"
    echo "Sandbox already exists, skipping creation."
  else
    echo "$create_output" >&2
    exit 1
  fi
}

# Setup SSH access to the claude-custom-ssh sandbox
sbx setup ssh --alias claude-custom-ssh.sbx

ssh -t claude-custom-ssh.sbx  "cd $(pwd) ; bash --login"

## Note: You have to manually stop the container when you are done with it.
## Otherwise it will keep running in the background. You can do this by running:
# sbx stop claude-custom-ssh
# sbx rm claude-custom-ssh --force
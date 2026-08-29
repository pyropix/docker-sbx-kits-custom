#!/usr/bin/env bash
set -euxo pipefail

# Setup GitHub secret for sbx. Overwrite existing secret if it exists.
gh auth token | sbx secret set github --force

# List available secrets
sbx secret ls

#!/usr/bin/env bash
# Convenience wrapper around sbx_setup.py --secret-gh.
# Prefer: uv run sbx_setup.py --secret-gh
set -euo pipefail

echo "Storing GitHub token as sbx secret..."

# Setup GitHub secret for sbx. Overwrite existing secret if it exists.
gh auth token | sbx secret set github --force

# List available secrets
sbx secret ls

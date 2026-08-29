#!/usr/bin/env bash
set -euo pipefail

command -v jq >/dev/null 2>&1 || exit 0

input=$(cat)
file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')

if [ -z "$file_path" ] || [ ! -f "$file_path" ]; then
    exit 0
fi

case "${file_path##*.}" in
    js|jsx|mjs|cjs|ts|tsx|mts|cts|css|scss|less|html|htm|json|jsonc|yaml|yml|md|mdx|graphql|gql|vue|hbs)
        ;;
    *)
        exit 0
        ;;
esac

prettier --write "$file_path" 2>/dev/null || true

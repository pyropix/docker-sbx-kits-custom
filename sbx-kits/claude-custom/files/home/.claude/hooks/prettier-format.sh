#!/usr/bin/env bash
set -euo pipefail

command -v jq >/dev/null 2>&1 || exit 0
command -v prettier >/dev/null 2>&1 || exit 0

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

# Exit 0 regardless so a prettier failure doesn't abort the Claude session,
# but leave stderr untouched so the agent sees errors (e.g. a syntax error it
# just wrote) on the hook's own stderr, not merged into its stdout.
prettier --write "$file_path" >/dev/null || true

#!/usr/bin/env bash
set -euo pipefail

input=$(cat)

file_path=$(python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
print(data.get('tool_input', {}).get('file_path', ''))
" <<< "$input")

if [ -z "$file_path" ] || [ ! -f "$file_path" ]; then
    exit 0
fi

prettier --write "$file_path" 2>/dev/null || true

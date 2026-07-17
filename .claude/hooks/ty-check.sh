#!/usr/bin/env bash
# PostToolUse hook: type-check Python files Claude just edited/wrote.
# Exits 2 (with details on stderr) if type errors remain, so Claude sees and fixes them.
set -euo pipefail

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

[[ "$file_path" == *.py ]] || exit 0
[[ -f "$file_path" ]] || exit 0

cd "$CLAUDE_PROJECT_DIR"

if ! output=$(uv run ty check "$file_path" 2>&1); then
  echo "$output" >&2
  exit 2
fi

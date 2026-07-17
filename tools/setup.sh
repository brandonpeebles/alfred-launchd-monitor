#!/bin/bash
# One-time dev setup: sync deps (incl. pre-commit) and install the git hooks.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

uv sync                                      # installs deps + the dev group (pre-commit)
uv run pre-commit install --install-hooks    # installs pre-commit + pre-push hooks per config

echo "setup complete: deps synced, pre-commit + pre-push hooks installed"

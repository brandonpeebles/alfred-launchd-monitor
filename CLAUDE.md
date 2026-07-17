# CLAUDE.md

Alfred 5 workflow that observes and controls macOS `launchd` LaunchAgents. See
`README.md` for user-facing usage and configuration.

## Setup

```bash
tools/setup.sh   # uv sync + install pre-commit / pre-push git hooks
```

## Commands

```bash
uv run pytest          # unit tests
uv run ruff check .    # lint
uv run ruff format .   # format
uv run ty check .      # type check
tools/package.sh       # rebuild the .alfredworkflow bundle
```

## Quality gates

Commits are gated by the [pre-commit](https://pre-commit.com) framework
(`.pre-commit-config.yaml`): the official Astral mirrors for ruff (lint + format)
and ty, the `uv-lock` hook, `sync-with-uv` (keeps the ruff/ty mirror revs pinned
to `uv.lock`), and the standard `pre-commit-hooks` hygiene set. **pytest runs at
the pre-push stage, not per-commit.** Don't hand-edit `.git/hooks` or reintroduce
`git config core.hooksPath` — the framework owns the hooks now.

The `.claude/hooks/*.sh` PostToolUse hooks additionally run ruff/ty per-file
during Claude edits for fast in-loop feedback; they complement the commit gate.

## Conventions

- **uv-native:** invoke all tools via `uv run`. Dev deps live in
  `[dependency-groups].dev`; `uv.lock` is committed.
- **Python version:** `requires-python = ">=3.9"` is the runtime floor — the
  workflow ships in the Alfred bundle and runs under whatever Python macOS
  provides. Dev is pinned to 3.11 (`.python-version`). Consequently
  `tools/build_info_plist.py` (a dev-only build script) imports `tomllib` with a
  `# ty: ignore[unresolved-import]`; do **not** bump `requires-python` to silence
  that.
- **Test fixtures:** `tests/fixtures/` holds captured `launchctl` output and is
  excluded from the whitespace/EOF fixers — don't reformat those files.

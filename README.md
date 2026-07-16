# Launchd Monitor (Alfred 5 workflow)

Observe and control your user-domain macOS `launchd` LaunchAgents from Alfred:
status at a glance, restart / load / unload / enable / disable, and tail or peek logs.

## Install

```bash
cd ~/src/alfred-launchd-monitor
tools/package.sh
open alfred-launchd-monitor.alfredworkflow   # double-click imports into Alfred
```

Alfred prompts for configuration on first import.

## Use

- Type `lj` to list jobs. Each row shows a status glyph, PID, last exit, and load state.
- **Enter** drills into a job's full action menu.
- On a list row: **⌘** restart · **⌥** tail log in terminal · **⌃** peek log in Alfred.

## Configuration (Alfred → workflow → [x] Configure Workflow)

| Var | Default | Meaning |
|---|---|---|
| `SCOPE` | `agents` | `agents` = `~/Library/LaunchAgents`; `gui` = all `launchctl list` labels |
| `LABEL_GLOB` | *(empty)* | e.g. `com.brandon.*` — narrows either scope |
| `AGENTS_DIR` | `~/Library/LaunchAgents` | plist source dir |
| `TERMINAL` | `ghostty` | `ghostty` \| `terminal` \| `iterm` |
| `LOG_TOOL` | `tail` | `tail` \| `less` \| `lnav` (falls back to `tail` if not installed) |
| `LOG_STREAM` | `out` | `out` \| `err` \| `both` |
| `LOG_LINES` | `200` | scrollback for peek/tail |

## Develop

```bash
uv run pytest          # unit tests
uv run ruff check .    # lint
uv run ruff format .   # format
tools/package.sh       # rebuild the .alfredworkflow
```

User `gui` domain only — no `sudo`/LaunchDaemons.

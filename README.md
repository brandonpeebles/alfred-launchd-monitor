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

- Type `lj` to list jobs. Each row shows a status glyph (🟢 running · ⚪ loaded/idle · 🔴 exited nonzero · ⚫ unloaded · 🚫 disabled), PID, and last exit.
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
| `LOG_STREAM` | `out` | `out` \| `err` |
| `LOG_LINES` | `200` | scrollback for peek/tail |

## Develop

One-time setup (installs deps + git hooks):

```bash
tools/setup.sh
```

Quality gates run automatically via [pre-commit](https://pre-commit.com): ruff
(lint + format), ty (type check), and standard hygiene hooks run on every commit;
the test suite runs at `git push`. Run them manually anytime:

```bash
uv run pre-commit run --all-files   # all commit-stage hooks
uv run pytest                       # unit tests (also gates git push)
tools/package.sh                    # rebuild the .alfredworkflow
```

`uv.lock` is committed to pin dev dependency versions for reproducible environments.

User `gui` domain only — no `sudo`/LaunchDaemons.

## Credits

Workflow icon: [Magnifying glass icons created by lakonicon - Flaticon](https://www.flaticon.com/free-icons/magnifying-glass).

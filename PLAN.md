
# Launchd Monitor — Alfred 5 Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an importable `.alfredworkflow` that lets the author observe and control user-domain `launchd` LaunchAgents from Alfred — status at a glance, restart/load/enable/disable, and tail/peek logs.

**Architecture:** A single stdlib-only Python 3 script (`launchd_monitor.py`) parses `launchctl`/`plistlib` output and emits Alfred Script Filter JSON for two chained Script Filters (`list` → `detail`). A thin Bash `bin/dispatch.sh` runs every mutating/terminal action as a single `launchctl`/`open` call, resolving log/plist paths back through the Python script so path logic has one source of truth. A tested `tools/build_info_plist.py` generates the Alfred object graph; `tools/package.sh` zips the bundle.

**Tech Stack:** Python 3 (stdlib: `plistlib`, `json`, `subprocess`, `pathlib`, `re`, `enum`, `dataclasses`), Bash, Alfred 5 workflow (`info.plist`), `uv`/`ruff`/`pytest` for dev tooling.

## Global Constraints

- **Runtime interpreter is macOS system `python3` (~3.9).** The runtime script (`launchd_monitor.py`, `tools/build_info_plist.py` is dev-only) MUST use only the standard library and MUST NOT use syntax newer than Python 3.9. Use `from __future__ import annotations` for `X | None` hints; use `class JobState(str, Enum)` not `StrEnum`; NO `match` statements; NO `X | Y` runtime unions in `isinstance`.
- **stdout of `launchd_monitor.py` is the Alfred interface.** It MUST emit only Alfred JSON (for `list`/`detail`) or a bare path/string (for `path`). All diagnostics go to **stderr** via `logging`. Never `print()` diagnostics.
- **PY-001 (binding).** Type-annotate all public function signatures; PEP 8 naming; `dataclasses` for structured data (not raw dicts); Google-style docstrings on public functions; `pathlib.Path` for paths with `encoding="utf-8"` on text I/O; no bare `except:`/`except Exception:` without re-raise — narrow `except` is allowed only around `subprocess`/`plistlib`/`int()` parsing; no mutable default args; f-strings only; `Enum` for fixed value sets.
- **Dev toolchain (PY-001):** `uv` for env, `ruff` for lint+format (`target-version = "py39"`), `pytest` for tests under `tests/unit/`. Mock at the boundary (`subprocess.run`, `plistlib.load`), never internal helpers. If `uv` cannot reach the network in a sandbox, fall back to a system `pytest`/`ruff` and note it — do not skip the test cycle.
- **Injection safety.** Python builds the item list; Bash receives `action:label` and passes label + resolved paths as **discrete argv elements**; `dispatch.sh` `case`-branches and never `eval`s. Domain target is always `gui/$(id -u)/<label>`.
- **User `gui` domain only.** No `sudo`, no system LaunchDaemons.
- **Project root:** `~/src/alfred-launchd-monitor/`. All paths below are relative to it unless absolute. This is a dedicated new git repo whose root **is** the project (there is no wrapper directory). Work on `main` (no worktree). Commit scoped file lists only.
- **Bundle id:** `com.brandon.launchd-monitor`. **Keyword:** `lj`.

---

## File Structure

```
alfred-launchd-monitor/
  pyproject.toml            # uv project + ruff + pytest config
  .python-version           # dev interpreter pin (3.11)
  launchd_monitor.py        # RUNTIME: list/detail/path subcommands, parse + emit Alfred JSON (stdlib only, 3.9-safe)
  bin/dispatch.sh           # RUNTIME: mutating actions + terminal/peek launch (thin bash)
  tools/build_info_plist.py # DEV: generate build/info.plist (Alfred object graph)
  tools/package.sh          # DEV: assemble build/ and zip → alfred-launchd-monitor.alfredworkflow
  icon.png                  # workflow icon (placeholder acceptable)
  README.md
  tests/
    unit/
      test_config.py
      test_state.py
      test_parsers.py
      test_plist.py
      test_print_parser.py
      test_subprocess.py
      test_discovery.py
      test_emit_list.py
      test_emit_detail.py
      test_main.py
      test_dispatch.py
      test_build_info_plist.py
    fixtures/
      launchctl_list.txt
      print_disabled.txt
      print_running.txt
      print_exited.txt
      sample.plist
```

**Responsibilities.** `launchd_monitor.py` is one focused module organized top-to-bottom: constants → dataclasses/enum → parsers → plist reader → subprocess wrappers → discovery/merge → Alfred emitters → `main()` dispatch. It stays in one file because the Alfred bundle invokes it directly and it must remain holdable in context (< ~450 lines). `dispatch.sh` owns only side-effecting `launchctl`/`open` calls. `tools/*` are dev-only and never shipped into the bundle except the generated `info.plist`.

---

### Task 1: Project scaffold + tooling

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `tests/unit/__init__.py` (empty)
- Create: `tests/unit/test_smoke.py`
- Create: `launchd_monitor.py` (module docstring + `__future__` import only)

**Interfaces:**
- Consumes: nothing.
- Produces: a runnable `uv run pytest` / `uv run ruff check .` cycle and an importable `launchd_monitor` module.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "alfred-launchd-monitor"
version = "0.1.0"
description = "Alfred 5 workflow to observe and control macOS launchd LaunchAgents"
requires-python = ">=3.9"

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6"]

[tool.ruff]
target-version = "py39"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Create `.python-version`**

```
3.11
```

- [ ] **Step 3: Create the module stub `launchd_monitor.py`**

```python
"""Alfred 5 workflow backend: parse launchd/launchctl state and emit Alfred JSON.

Runtime interpreter is macOS system python3 (~3.9); use only the standard library
and no syntax newer than 3.9. stdout is the Alfred interface — diagnostics go to stderr.
"""

from __future__ import annotations
```

- [ ] **Step 4: Write the smoke test** in `tests/unit/test_smoke.py`

```python
import launchd_monitor


def test_module_imports():
    assert launchd_monitor is not None
```

- [ ] **Step 5: Run the test cycle**

Run: `cd ~/src/alfred-launchd-monitor && uv run pytest tests/unit/test_smoke.py -v`
Expected: PASS. Then `uv run ruff check .` → no errors.

(If `uv` is network-blocked in a sandbox: `python3 -m pytest tests/unit/test_smoke.py -v` and `ruff check .` if a system `ruff` exists; note the fallback in the commit message.)

- [ ] **Step 6: Commit**

```bash
cd ~/src/alfred-launchd-monitor
git add pyproject.toml .python-version \
  launchd_monitor.py tests/unit/__init__.py \
  tests/unit/test_smoke.py
git commit -m "chore(launchd-monitor): scaffold uv/ruff/pytest project"
```

---

### Task 2: Config from environment variables

**Files:**
- Modify: `launchd_monitor.py` (append `Config` + `_parse_int`)
- Create: `tests/unit/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Config` frozen dataclass with fields `scope: str`, `label_glob: str`, `agents_dir: Path`, `terminal: str`, `log_tool: str`, `log_stream: str`, `log_lines: int`.
  - `Config.from_env(env: Mapping[str, str]) -> Config`.

- [ ] **Step 1: Write the failing test** in `tests/unit/test_config.py`

```python
from pathlib import Path

from launchd_monitor import Config


def test_from_env_defaults():
    cfg = Config.from_env({})
    assert cfg.scope == "agents"
    assert cfg.label_glob == ""
    assert cfg.agents_dir == Path("~/Library/LaunchAgents").expanduser()
    assert cfg.terminal == "ghostty"
    assert cfg.log_tool == "tail"
    assert cfg.log_stream == "out"
    assert cfg.log_lines == 200


def test_from_env_overrides_and_expands():
    cfg = Config.from_env(
        {
            "SCOPE": "gui",
            "LABEL_GLOB": "com.brandon.*",
            "AGENTS_DIR": "~/Custom/Agents",
            "TERMINAL": "iterm",
            "LOG_TOOL": "lnav",
            "LOG_STREAM": "both",
            "LOG_LINES": "50",
        }
    )
    assert cfg.scope == "gui"
    assert cfg.label_glob == "com.brandon.*"
    assert cfg.agents_dir == Path("~/Custom/Agents").expanduser()
    assert cfg.terminal == "iterm"
    assert cfg.log_tool == "lnav"
    assert cfg.log_stream == "both"
    assert cfg.log_lines == 50


def test_from_env_bad_log_lines_falls_back():
    assert Config.from_env({"LOG_LINES": "notanumber"}).log_lines == 200
    assert Config.from_env({"LOG_LINES": ""}).log_lines == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: FAIL with `ImportError: cannot import name 'Config'`.

- [ ] **Step 3: Implement** — append to `launchd_monitor.py` (after the `__future__` import, keep imports grouped at top of file):

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


def _parse_int(value: "str | None", default: int) -> int:
    """Parse an int from an env string, returning default on missing/invalid input."""
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    """Resolved workflow configuration sourced from Alfred config-sheet env vars."""

    scope: str
    label_glob: str
    agents_dir: Path
    terminal: str
    log_tool: str
    log_stream: str
    log_lines: int

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Config":
        """Build a Config from an environment mapping, applying documented defaults."""
        return cls(
            scope=env.get("SCOPE") or "agents",
            label_glob=env.get("LABEL_GLOB") or "",
            agents_dir=Path(env.get("AGENTS_DIR") or "~/Library/LaunchAgents").expanduser(),
            terminal=env.get("TERMINAL") or "ghostty",
            log_tool=env.get("LOG_TOOL") or "tail",
            log_stream=env.get("LOG_STREAM") or "out",
            log_lines=_parse_int(env.get("LOG_LINES"), 200),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_config.py -v` → PASS. `uv run ruff check .` → clean.

- [ ] **Step 5: Commit**

```bash
git add launchd_monitor.py tests/unit/test_config.py
git commit -m "feat(launchd-monitor): resolve config from env vars"
```

---

### Task 3: Job state model + glyphs

**Files:**
- Modify: `launchd_monitor.py` (append `JobState`, `glyph`, `JobRecord`)
- Create: `tests/unit/test_state.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `class JobState(str, Enum)` with members `RUNNING="running"`, `IDLE="loaded (idle)"`, `EXITED="exited"`, `UNLOADED="unloaded"`, `DISABLED="disabled"`.
  - `glyph(state: JobState) -> str`.
  - `JobRecord` frozen dataclass: `label: str`, `plist_path: Path | None`, `pid: int | None`, `last_exit_code: int | None`, `loaded: bool`, `disabled: bool`, `stdout_path: str | None`, `stderr_path: str | None`; property `state -> JobState`; method `subtitle() -> str`.

- [ ] **Step 1: Write the failing test** in `tests/unit/test_state.py`

```python
from launchd_monitor import JobRecord, JobState, glyph


def _rec(**kw):
    base = dict(
        label="com.brandon.job",
        plist_path=None,
        pid=None,
        last_exit_code=0,
        loaded=True,
        disabled=False,
        stdout_path=None,
        stderr_path=None,
    )
    base.update(kw)
    return JobRecord(**base)


def test_state_precedence():
    assert _rec(disabled=True, loaded=False).state is JobState.DISABLED
    assert _rec(loaded=False).state is JobState.UNLOADED
    assert _rec(pid=4821).state is JobState.RUNNING
    assert _rec(pid=None, last_exit_code=78).state is JobState.EXITED
    assert _rec(pid=None, last_exit_code=0).state is JobState.IDLE


def test_glyphs():
    assert glyph(JobState.RUNNING) == "🟢"
    assert glyph(JobState.IDLE) == "⚪"
    assert glyph(JobState.EXITED) == "🔴"
    assert glyph(JobState.UNLOADED) == "⚫"
    assert glyph(JobState.DISABLED) == "🚫"


def test_subtitle():
    sub = _rec(pid=4821, last_exit_code=0).subtitle()
    assert sub == "🟢 running · PID 4821 · exit 0 · loaded"
    assert _rec(pid=None, last_exit_code=78).subtitle() == "🔴 exited · exit 78 · loaded"
    assert _rec(loaded=False, last_exit_code=None).subtitle() == "⚫ unloaded · unloaded"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_state.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement** — append to `launchd_monitor.py` (add `from enum import Enum` to the import group):

```python
from enum import Enum


class JobState(str, Enum):
    """Derived lifecycle state of a launchd job."""

    RUNNING = "running"
    IDLE = "loaded (idle)"
    EXITED = "exited"
    UNLOADED = "unloaded"
    DISABLED = "disabled"


_GLYPHS = {
    JobState.RUNNING: "🟢",
    JobState.IDLE: "⚪",
    JobState.EXITED: "🔴",
    JobState.UNLOADED: "⚫",
    JobState.DISABLED: "🚫",
}


def glyph(state: JobState) -> str:
    """Return the status emoji for a job state."""
    return _GLYPHS[state]


@dataclass(frozen=True)
class JobRecord:
    """A launchd job merged from plist source and runtime status, for the list view."""

    label: str
    plist_path: "Path | None"
    pid: "int | None"
    last_exit_code: "int | None"
    loaded: bool
    disabled: bool
    stdout_path: "str | None"
    stderr_path: "str | None"

    @property
    def state(self) -> JobState:
        """Derive display state; precedence disabled > unloaded > running > exited > idle."""
        if self.disabled:
            return JobState.DISABLED
        if not self.loaded:
            return JobState.UNLOADED
        if self.pid is not None:
            return JobState.RUNNING
        if self.last_exit_code:
            return JobState.EXITED
        return JobState.IDLE

    def subtitle(self) -> str:
        """Build the Alfred row subtitle: glyph · state · PID · exit · load state."""
        state = self.state
        parts = [f"{glyph(state)} {state.value}"]
        if self.pid is not None:
            parts.append(f"PID {self.pid}")
        if self.last_exit_code is not None:
            parts.append(f"exit {self.last_exit_code}")
        parts.append("disabled" if self.disabled else ("loaded" if self.loaded else "unloaded"))
        return " · ".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_state.py -v` → PASS. `uv run ruff check .` → clean.

- [ ] **Step 5: Commit**

```bash
git add launchd_monitor.py tests/unit/test_state.py
git commit -m "feat(launchd-monitor): job state model, glyphs, subtitle"
```

---

### Task 4: `launchctl list` + `print-disabled` parsers

**Files:**
- Modify: `launchd_monitor.py` (append `ListEntry`, `parse_launchctl_list`, `parse_print_disabled`)
- Create: `tests/fixtures/launchctl_list.txt`, `tests/fixtures/print_disabled.txt`
- Create: `tests/unit/test_parsers.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ListEntry` frozen dataclass: `label: str`, `pid: int | None`, `last_status: int`.
  - `parse_launchctl_list(output: str) -> dict[str, ListEntry]` (keyed by label).
  - `parse_print_disabled(output: str) -> dict[str, bool]` (label → disabled).

- [ ] **Step 1: Create fixtures**

`tests/fixtures/launchctl_list.txt` (tab-separated, real `launchctl list` shape):

```
PID	Status	Label
-	0	com.brandon.morning-brief
4821	0	com.brandon.running-job
-	78	com.brandon.failing-job
-	0	com.apple.some.service
```

`tests/fixtures/print_disabled.txt`:

```
disabled services = {
	"com.brandon.morning-brief" => false
	"com.brandon.disabled-job" => true
}
```

- [ ] **Step 2: Write the failing test** in `tests/unit/test_parsers.py`

```python
from pathlib import Path

from launchd_monitor import parse_launchctl_list, parse_print_disabled

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_launchctl_list():
    entries = parse_launchctl_list((FIXTURES / "launchctl_list.txt").read_text(encoding="utf-8"))
    assert set(entries) == {
        "com.brandon.morning-brief",
        "com.brandon.running-job",
        "com.brandon.failing-job",
        "com.apple.some.service",
    }
    assert entries["com.brandon.running-job"].pid == 4821
    assert entries["com.brandon.morning-brief"].pid is None
    assert entries["com.brandon.failing-job"].last_status == 78


def test_parse_launchctl_list_ignores_header_and_blanks():
    assert parse_launchctl_list("PID\tStatus\tLabel\n\n") == {}


def test_parse_print_disabled():
    disabled = parse_print_disabled(
        (FIXTURES / "print_disabled.txt").read_text(encoding="utf-8")
    )
    assert disabled == {
        "com.brandon.morning-brief": False,
        "com.brandon.disabled-job": True,
    }
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_parsers.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 4: Implement** — append to `launchd_monitor.py` (add `import re` to imports):

```python
import re

_DISABLED_RE = re.compile(r'"(?P<label>[^"]+)"\s*=>\s*(?P<val>true|false)')


@dataclass(frozen=True)
class ListEntry:
    """One row of `launchctl list`: label, current PID (if running), last exit status."""

    label: str
    pid: "int | None"
    last_status: int


def parse_launchctl_list(output: str) -> "dict[str, ListEntry]":
    """Parse `launchctl list` output into label -> ListEntry, skipping the header row."""
    entries: "dict[str, ListEntry]" = {}
    for line in output.splitlines():
        if not line.strip() or line.startswith("PID"):
            continue
        cols = line.split("\t")
        if len(cols) < 3:
            cols = line.split(None, 2)
        if len(cols) < 3:
            continue
        pid_s, status_s, label = cols[0], cols[1], cols[2].strip()
        pid = int(pid_s) if pid_s.isdigit() else None
        try:
            status = int(status_s)
        except ValueError:
            status = 0
        entries[label] = ListEntry(label=label, pid=pid, last_status=status)
    return entries


def parse_print_disabled(output: str) -> "dict[str, bool]":
    """Parse `launchctl print-disabled` output into label -> disabled bool."""
    return {m.group("label"): m.group("val") == "true" for m in _DISABLED_RE.finditer(output)}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_parsers.py -v` → PASS. `uv run ruff check .` → clean.

- [ ] **Step 6: Commit**

```bash
git add launchd_monitor.py tests/unit/test_parsers.py \
  tests/fixtures/launchctl_list.txt tests/fixtures/print_disabled.txt
git commit -m "feat(launchd-monitor): parse launchctl list and print-disabled"
```

---

### Task 5: plist reader

**Files:**
- Modify: `launchd_monitor.py` (append `PlistInfo`, `read_plist`)
- Create: `tests/fixtures/sample.plist`
- Create: `tests/unit/test_plist.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `PlistInfo` frozen dataclass: `label: str | None`, `stdout_path: str | None`, `stderr_path: str | None`, `program_arguments: list[str]`, `working_dir: str | None`.
  - `read_plist(path: Path) -> PlistInfo` — raises `OSError` / `plistlib.InvalidFileException` on unreadable/corrupt files (callers catch).

- [ ] **Step 1: Create fixture** `tests/fixtures/sample.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>com.brandon.morning-brief</string>
	<key>ProgramArguments</key>
	<array>
		<string>/usr/bin/python3</string>
		<string>/Users/brandon/bin/brief.py</string>
	</array>
	<key>StandardOutPath</key>
	<string>/Users/brandon/Library/Logs/morning-brief.out.log</string>
	<key>StandardErrorPath</key>
	<string>/Users/brandon/Library/Logs/morning-brief.err.log</string>
	<key>WorkingDirectory</key>
	<string>/Users/brandon</string>
</dict>
</plist>
```

- [ ] **Step 2: Write the failing test** in `tests/unit/test_plist.py`

```python
from pathlib import Path

import pytest

from launchd_monitor import read_plist

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_read_plist():
    info = read_plist(FIXTURES / "sample.plist")
    assert info.label == "com.brandon.morning-brief"
    assert info.stdout_path == "/Users/brandon/Library/Logs/morning-brief.out.log"
    assert info.stderr_path == "/Users/brandon/Library/Logs/morning-brief.err.log"
    assert info.program_arguments == ["/usr/bin/python3", "/Users/brandon/bin/brief.py"]
    assert info.working_dir == "/Users/brandon"


def test_read_plist_missing_file_raises():
    with pytest.raises(OSError):
        read_plist(FIXTURES / "does-not-exist.plist")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_plist.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 4: Implement** — append to `launchd_monitor.py` (add `import plistlib` to imports):

```python
import plistlib


@dataclass(frozen=True)
class PlistInfo:
    """Fields read from a LaunchAgent .plist (source of truth for log paths)."""

    label: "str | None"
    stdout_path: "str | None"
    stderr_path: "str | None"
    program_arguments: "list[str]"
    working_dir: "str | None"


def read_plist(path: Path) -> PlistInfo:
    """Read a LaunchAgent plist. Raises OSError / plistlib.InvalidFileException on failure."""
    with path.open("rb") as handle:
        data = plistlib.load(handle)
    return PlistInfo(
        label=data.get("Label"),
        stdout_path=data.get("StandardOutPath"),
        stderr_path=data.get("StandardErrorPath"),
        program_arguments=list(data.get("ProgramArguments", [])),
        working_dir=data.get("WorkingDirectory"),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_plist.py -v` → PASS. `uv run ruff check .` → clean.

- [ ] **Step 6: Commit**

```bash
git add launchd_monitor.py tests/unit/test_plist.py \
  tests/fixtures/sample.plist
git commit -m "feat(launchd-monitor): read LaunchAgent plists"
```

---

### Task 6: `launchctl print` detail parser

**Files:**
- Modify: `launchd_monitor.py` (append `PrintInfo`, `parse_launchctl_print`)
- Create: `tests/fixtures/print_running.txt`, `tests/fixtures/print_exited.txt`
- Create: `tests/unit/test_print_parser.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `PrintInfo` frozen dataclass: `plist_path: str | None`, `pid: int | None`, `last_exit_code: int | None`, `state: str | None`, `program_arguments: list[str]`, `stdout_path: str | None`, `stderr_path: str | None`, `working_dir: str | None`.
  - `parse_launchctl_print(output: str) -> PrintInfo` — returns an all-`None`/empty `PrintInfo` when `output` is empty (job not loaded).

- [ ] **Step 1: Create fixtures**

`tests/fixtures/print_running.txt`:

```
com.brandon.running-job = {
	active count = 1
	path = /Users/brandon/Library/LaunchAgents/com.brandon.running-job.plist
	state = running
	program = /usr/bin/python3
	arguments = {
		/usr/bin/python3
		/Users/brandon/bin/job.py
	}
	working directory = /Users/brandon
	stdout path = /Users/brandon/Library/Logs/job.out.log
	stderr path = /Users/brandon/Library/Logs/job.err.log
	pid = 4821
	last exit code = 0
}
```

`tests/fixtures/print_exited.txt`:

```
com.brandon.failing-job = {
	active count = 0
	path = /Users/brandon/Library/LaunchAgents/com.brandon.failing-job.plist
	state = not running
	last exit code = 78
}
```

- [ ] **Step 2: Write the failing test** in `tests/unit/test_print_parser.py`

```python
from pathlib import Path

from launchd_monitor import parse_launchctl_print

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_print_running():
    info = parse_launchctl_print((FIXTURES / "print_running.txt").read_text(encoding="utf-8"))
    assert info.plist_path == "/Users/brandon/Library/LaunchAgents/com.brandon.running-job.plist"
    assert info.pid == 4821
    assert info.last_exit_code == 0
    assert info.state == "running"
    assert info.program_arguments == ["/usr/bin/python3", "/Users/brandon/bin/job.py"]
    assert info.stdout_path == "/Users/brandon/Library/Logs/job.out.log"
    assert info.stderr_path == "/Users/brandon/Library/Logs/job.err.log"
    assert info.working_dir == "/Users/brandon"


def test_parse_print_exited():
    info = parse_launchctl_print((FIXTURES / "print_exited.txt").read_text(encoding="utf-8"))
    assert info.pid is None
    assert info.last_exit_code == 78
    assert info.state == "not running"
    assert info.program_arguments == []
    assert info.stdout_path is None


def test_parse_print_empty():
    info = parse_launchctl_print("")
    assert info.pid is None
    assert info.plist_path is None
    assert info.program_arguments == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_print_parser.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 4: Implement** — append to `launchd_monitor.py`:

```python
@dataclass(frozen=True)
class PrintInfo:
    """Fields extracted from `launchctl print gui/<uid>/<label>` output."""

    plist_path: "str | None"
    pid: "int | None"
    last_exit_code: "int | None"
    state: "str | None"
    program_arguments: "list[str]"
    stdout_path: "str | None"
    stderr_path: "str | None"
    working_dir: "str | None"


def _find_scalar(output: str, key: str) -> "str | None":
    """Return the RHS of a `<key> = <value>` line in launchctl print output, or None."""
    match = re.search(rf"^\s*{re.escape(key)}\s*=\s*(.+?)\s*$", output, re.MULTILINE)
    return match.group(1) if match else None


def _find_int(output: str, key: str) -> "int | None":
    """Return the int RHS of a `<key> = <int>` line, or None if absent/non-numeric."""
    raw = _find_scalar(output, key)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def parse_launchctl_print(output: str) -> PrintInfo:
    """Parse `launchctl print` output. Returns an empty PrintInfo when output is blank."""
    program_arguments: "list[str]" = []
    args_block = re.search(r"arguments\s*=\s*\{(.*?)\}", output, re.DOTALL)
    if args_block:
        for line in args_block.group(1).splitlines():
            token = line.strip().strip('"')
            if token:
                program_arguments.append(token)
    return PrintInfo(
        plist_path=_find_scalar(output, "path"),
        pid=_find_int(output, "pid"),
        last_exit_code=_find_int(output, "last exit code"),
        state=_find_scalar(output, "state"),
        program_arguments=program_arguments,
        stdout_path=_find_scalar(output, "stdout path"),
        stderr_path=_find_scalar(output, "stderr path"),
        working_dir=_find_scalar(output, "working directory"),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_print_parser.py -v` → PASS. `uv run ruff check .` → clean.

- [ ] **Step 6: Commit**

```bash
git add launchd_monitor.py tests/unit/test_print_parser.py \
  tests/fixtures/print_running.txt tests/fixtures/print_exited.txt
git commit -m "feat(launchd-monitor): parse launchctl print detail output"
```

---

### Task 7: subprocess wrappers (boundary)

**Files:**
- Modify: `launchd_monitor.py` (append constants + `_run`, `launchctl_list`, `print_disabled`, `launchctl_print`)
- Create: `tests/unit/test_subprocess.py`

**Interfaces:**
- Consumes: `parse_launchctl_list`, `parse_print_disabled`, `parse_launchctl_print`.
- Produces:
  - Module constants `LAUNCHCTL = "/bin/launchctl"`, `_SAFE_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"`.
  - `_run(args: list[str]) -> subprocess.CompletedProcess` (sets explicit `PATH`, `text=True`, `check=False`).
  - `launchctl_list() -> dict[str, ListEntry]`.
  - `print_disabled(uid: int) -> dict[str, bool]`.
  - `launchctl_print(uid: int, label: str) -> PrintInfo`.

- [ ] **Step 1: Write the failing test** in `tests/unit/test_subprocess.py`

```python
import subprocess

import launchd_monitor as lm


def _fake_completed(stdout):
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def test_launchctl_list_uses_boundary(monkeypatch):
    calls = {}

    def fake_run(args, **kwargs):
        calls["args"] = args
        calls["path"] = kwargs["env"]["PATH"]
        return _fake_completed("PID\tStatus\tLabel\n4821\t0\tcom.brandon.running-job\n")

    monkeypatch.setattr(lm.subprocess, "run", fake_run)
    entries = lm.launchctl_list()
    assert calls["args"] == ["/bin/launchctl", "list"]
    assert calls["path"] == "/usr/bin:/bin:/usr/sbin:/sbin"
    assert entries["com.brandon.running-job"].pid == 4821


def test_launchctl_print_builds_target(monkeypatch):
    seen = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        return _fake_completed("com.brandon.running-job = {\n\tpid = 4821\n}\n")

    monkeypatch.setattr(lm.subprocess, "run", fake_run)
    info = lm.launchctl_print(501, "com.brandon.running-job")
    assert seen["args"] == ["/bin/launchctl", "print", "gui/501/com.brandon.running-job"]
    assert info.pid == 4821


def test_print_disabled_builds_target(monkeypatch):
    seen = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        return _fake_completed('disabled services = {\n\t"com.brandon.x" => true\n}\n')

    monkeypatch.setattr(lm.subprocess, "run", fake_run)
    disabled = lm.print_disabled(501)
    assert seen["args"] == ["/bin/launchctl", "print-disabled", "gui/501"]
    assert disabled == {"com.brandon.x": True}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_subprocess.py -v`
Expected: FAIL with `AttributeError`/`ImportError`.

- [ ] **Step 3: Implement** — append to `launchd_monitor.py` (add `import os`, `import subprocess` to imports):

```python
import os
import subprocess

LAUNCHCTL = "/bin/launchctl"
_SAFE_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"


def _run(args: "list[str]") -> "subprocess.CompletedProcess":
    """Run a command with an explicit minimal PATH (Alfred's env is minimal)."""
    env = {**os.environ, "PATH": _SAFE_PATH}
    return subprocess.run(args, capture_output=True, text=True, env=env, check=False)


def launchctl_list() -> "dict[str, ListEntry]":
    """Return label -> ListEntry from `launchctl list`."""
    return parse_launchctl_list(_run([LAUNCHCTL, "list"]).stdout)


def print_disabled(uid: int) -> "dict[str, bool]":
    """Return label -> disabled bool from `launchctl print-disabled gui/<uid>`."""
    return parse_print_disabled(_run([LAUNCHCTL, "print-disabled", f"gui/{uid}"]).stdout)


def launchctl_print(uid: int, label: str) -> PrintInfo:
    """Return parsed detail from `launchctl print gui/<uid>/<label>` (empty if not loaded)."""
    return parse_launchctl_print(_run([LAUNCHCTL, "print", f"gui/{uid}/{label}"]).stdout)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_subprocess.py -v` → PASS. `uv run ruff check .` → clean.

- [ ] **Step 5: Commit**

```bash
git add launchd_monitor.py tests/unit/test_subprocess.py
git commit -m "feat(launchd-monitor): launchctl subprocess wrappers"
```

---

### Task 8: job discovery + record merge

**Files:**
- Modify: `launchd_monitor.py` (append `discover_pairs`, `build_job_record`, `build_records`)
- Create: `tests/unit/test_discovery.py`

**Interfaces:**
- Consumes: `Config`, `ListEntry`, `PlistInfo`, `JobRecord`, `read_plist`.
- Produces:
  - `discover_pairs(config: Config, list_entries: dict[str, ListEntry]) -> list[tuple[str, Path | None]]` — from plist glob (agents scope) or `launchctl list` labels (gui scope), filtered by `label_glob` via `fnmatch`.
  - `build_job_record(label: str, plist_path: Path | None, list_entries: dict[str, ListEntry], disabled_map: dict[str, bool], plist_info: PlistInfo | None) -> JobRecord`.
  - `build_records(config: Config, query: str = "") -> list[JobRecord]` — the full list pipeline (calls `launchctl_list`, `print_disabled`, `discover_pairs`, per-plist `read_plist`), substring-filtered by `query`.

- [ ] **Step 1: Write the failing test** in `tests/unit/test_discovery.py`

```python
from pathlib import Path

import launchd_monitor as lm
from launchd_monitor import Config, ListEntry, PlistInfo, build_job_record, discover_pairs


def test_discover_pairs_gui_scope():
    cfg = Config.from_env({"SCOPE": "gui"})
    entries = {"com.a": ListEntry("com.a", None, 0), "com.b": ListEntry("com.b", 1, 0)}
    pairs = discover_pairs(cfg, entries)
    assert pairs == [("com.a", None), ("com.b", None)]


def test_discover_pairs_gui_scope_glob_filter():
    cfg = Config.from_env({"SCOPE": "gui", "LABEL_GLOB": "com.brandon.*"})
    entries = {
        "com.brandon.x": ListEntry("com.brandon.x", None, 0),
        "com.apple.y": ListEntry("com.apple.y", None, 0),
    }
    assert discover_pairs(cfg, entries) == [("com.brandon.x", None)]


def test_discover_pairs_agents_scope(tmp_path, monkeypatch):
    plist = tmp_path / "com.brandon.job.plist"
    plist.write_bytes(b"")  # content irrelevant; read_plist is stubbed
    monkeypatch.setattr(
        lm, "read_plist", lambda p: PlistInfo("com.brandon.job", None, None, [], None)
    )
    cfg = Config.from_env({"SCOPE": "agents", "AGENTS_DIR": str(tmp_path)})
    assert discover_pairs(cfg, {}) == [("com.brandon.job", plist)]


def test_discover_pairs_agents_scope_skips_unreadable(tmp_path, monkeypatch):
    (tmp_path / "bad.plist").write_bytes(b"")

    def boom(_p):
        raise ValueError("corrupt")

    monkeypatch.setattr(lm, "read_plist", boom)
    cfg = Config.from_env({"SCOPE": "agents", "AGENTS_DIR": str(tmp_path)})
    assert discover_pairs(cfg, {}) == []


def test_build_job_record_running():
    entries = {"com.a": ListEntry("com.a", 4821, 0)}
    rec = build_job_record("com.a", Path("/x.plist"), entries, {}, None)
    assert rec.loaded is True
    assert rec.pid == 4821
    assert rec.state.value == "running"


def test_build_job_record_unloaded_disabled():
    rec = build_job_record("com.a", None, {}, {"com.a": True}, None)
    assert rec.loaded is False
    assert rec.disabled is True
    assert rec.state.value == "disabled"
```

> Note: `discover_pairs` must catch a broad parse failure from a stubbed `read_plist` (the test raises `ValueError`). Catch `(OSError, plistlib.InvalidFileException, ValueError)` — plist corruption surfaces as any of these.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_discovery.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement** — append to `launchd_monitor.py` (add `import fnmatch` to imports):

```python
import fnmatch

_PLIST_ERRORS = (OSError, plistlib.InvalidFileException, ValueError)


def discover_pairs(
    config: Config, list_entries: "dict[str, ListEntry]"
) -> "list[tuple[str, Path | None]]":
    """Discover (label, plist_path) pairs from the configured scope, filtered by label_glob."""
    pairs: "list[tuple[str, Path | None]]" = []
    if config.scope == "gui":
        pairs = [(label, None) for label in sorted(list_entries)]
    else:
        for path in sorted(config.agents_dir.glob("*.plist")):
            try:
                info = read_plist(path)
            except _PLIST_ERRORS:
                continue
            pairs.append((info.label or path.stem, path))
    if config.label_glob:
        pairs = [(lbl, p) for (lbl, p) in pairs if fnmatch.fnmatch(lbl, config.label_glob)]
    return pairs


def build_job_record(
    label: str,
    plist_path: "Path | None",
    list_entries: "dict[str, ListEntry]",
    disabled_map: "dict[str, bool]",
    plist_info: "PlistInfo | None",
) -> JobRecord:
    """Merge plist source and runtime status into a JobRecord for the list view."""
    entry = list_entries.get(label)
    return JobRecord(
        label=label,
        plist_path=plist_path,
        pid=entry.pid if entry else None,
        last_exit_code=entry.last_status if entry else None,
        loaded=entry is not None,
        disabled=disabled_map.get(label, False),
        stdout_path=plist_info.stdout_path if plist_info else None,
        stderr_path=plist_info.stderr_path if plist_info else None,
    )


def build_records(config: Config, query: str = "") -> "list[JobRecord]":
    """Run the full list pipeline: gather runtime status, discover, merge, filter by query."""
    list_entries = launchctl_list()
    disabled_map = print_disabled(os.getuid())
    pairs = discover_pairs(config, list_entries)
    if query:
        needle = query.lower()
        pairs = [(lbl, p) for (lbl, p) in pairs if needle in lbl.lower()]
    records: "list[JobRecord]" = []
    for label, plist_path in pairs:
        info: "PlistInfo | None" = None
        if plist_path is not None:
            try:
                info = read_plist(plist_path)
            except _PLIST_ERRORS:
                info = None
        records.append(build_job_record(label, plist_path, list_entries, disabled_map, info))
    return records
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_discovery.py -v` → PASS. `uv run ruff check .` → clean.

- [ ] **Step 5: Commit**

```bash
git add launchd_monitor.py tests/unit/test_discovery.py
git commit -m "feat(launchd-monitor): discover jobs and merge into records"
```

---

### Task 9: Alfred `list` emitter

**Files:**
- Modify: `launchd_monitor.py` (append `emit_list`)
- Create: `tests/unit/test_emit_list.py`

**Interfaces:**
- Consumes: `JobRecord`, `Config`.
- Produces: `emit_list(records: list[JobRecord], config: Config) -> dict` — Alfred `{"items": [...]}`. Empty records → a single `valid=false` "no matches" item (never empty JSON). Each real item carries default `arg = label` (→ detail) and `mods` for `cmd`/`alt`/`ctrl` with action-prefixed args.

- [ ] **Step 1: Write the failing test** in `tests/unit/test_emit_list.py`

```python
from launchd_monitor import Config, JobRecord, emit_list


def _rec(label="com.brandon.job"):
    return JobRecord(label, None, 4821, 0, True, False, None, None)


def test_emit_list_item_shape():
    out = emit_list([_rec()], Config.from_env({}))
    item = out["items"][0]
    assert item["title"] == "com.brandon.job"
    assert item["arg"] == "com.brandon.job"
    assert item["valid"] is True
    assert item["mods"]["cmd"]["arg"] == "restart:com.brandon.job"
    assert item["mods"]["alt"]["arg"] == "tail-term:com.brandon.job"
    assert item["mods"]["ctrl"]["arg"] == "peek:com.brandon.job"


def test_emit_list_empty_returns_placeholder():
    out = emit_list([], Config.from_env({"LABEL_GLOB": "com.nope.*"}))
    assert len(out["items"]) == 1
    only = out["items"][0]
    assert only["valid"] is False
    assert "com.nope.*" in only["title"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_emit_list.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement** — append to `launchd_monitor.py`:

```python
def emit_list(records: "list[JobRecord]", config: Config) -> dict:
    """Build the Alfred Script Filter payload for the job list view."""
    if not records:
        pattern = config.label_glob or "*"
        return {
            "items": [
                {
                    "title": f"No launchd jobs match “{pattern}”",
                    "subtitle": f"scope={config.scope} · adjust SCOPE / LABEL_GLOB in config",
                    "valid": False,
                }
            ]
        }
    items = []
    for record in records:
        label = record.label
        items.append(
            {
                "uid": label,
                "title": label,
                "subtitle": record.subtitle(),
                "arg": label,
                "valid": True,
                "mods": {
                    "cmd": {"arg": f"restart:{label}", "subtitle": "↻ Restart (kickstart -k)"},
                    "alt": {"arg": f"tail-term:{label}", "subtitle": "\U0001f4df Tail log in terminal"},
                    "ctrl": {"arg": f"peek:{label}", "subtitle": "\U0001f441 Peek log in Alfred"},
                },
            }
        )
    return {"items": items}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_emit_list.py -v` → PASS. `uv run ruff check .` → clean.

- [ ] **Step 5: Commit**

```bash
git add launchd_monitor.py tests/unit/test_emit_list.py
git commit -m "feat(launchd-monitor): emit Alfred list JSON with modifiers"
```

---

### Task 10: `JobDetail` + Alfred `detail` emitter

**Files:**
- Modify: `launchd_monitor.py` (append `JobDetail`, `build_detail`, `_detail_row`, `emit_detail`, `resolve_path`)
- Create: `tests/unit/test_emit_detail.py`

**Interfaces:**
- Consumes: `Config`, `PrintInfo`, `PlistInfo`, `launchctl_print`, `launchctl_list`, `print_disabled`, `read_plist`, `JobState`, `glyph`.
- Produces:
  - `JobDetail` frozen dataclass: `label: str`, `plist_path: Path | None`, `pid: int | None`, `last_exit_code: int | None`, `loaded: bool`, `disabled: bool`, `stdout_path: str | None`, `stderr_path: str | None`, `program_arguments: list[str]`, `working_dir: str | None`; property `state -> JobState`; method `summary() -> str`.
  - `build_detail(config: Config, label: str) -> JobDetail`.
  - `emit_detail(detail: JobDetail) -> dict` — contextual action rows; each actionable row `arg = "<action>:<label>"`, row 0 is `valid=false` summary.
  - `resolve_path(config: Config, label: str, kind: str) -> str` where `kind ∈ {"plist","out","err"}`; returns the resolved path or `""`. Used by the `path` subcommand (Task 11) and `dispatch.sh`.

- [ ] **Step 1: Write the failing test** in `tests/unit/test_emit_detail.py`

```python
from pathlib import Path

from launchd_monitor import JobDetail, emit_detail


def _detail(**kw):
    base = dict(
        label="com.brandon.job",
        plist_path=Path("/x.plist"),
        pid=4821,
        last_exit_code=0,
        loaded=True,
        disabled=False,
        stdout_path="/logs/out.log",
        stderr_path="/logs/err.log",
        program_arguments=["/usr/bin/python3", "/x.py"],
        working_dir="/home",
    )
    base.update(kw)
    return JobDetail(**base)


def _args(out):
    return [i.get("arg") for i in out["items"]]


def test_detail_summary_row_first_and_invalid():
    out = emit_detail(_detail())
    assert out["items"][0]["valid"] is False
    assert out["items"][0]["title"].startswith("🟢 running")


def test_detail_loaded_shows_unload_not_load():
    args = _args(emit_detail(_detail(loaded=True)))
    assert "unload:com.brandon.job" in args
    assert "load:com.brandon.job" not in args


def test_detail_unloaded_shows_load_not_unload():
    args = _args(emit_detail(_detail(loaded=False, pid=None)))
    assert "load:com.brandon.job" in args
    assert "unload:com.brandon.job" not in args


def test_detail_enabled_shows_disable_only():
    args = _args(emit_detail(_detail(disabled=False)))
    assert "disable:com.brandon.job" in args
    assert "enable:com.brandon.job" not in args


def test_detail_disabled_shows_enable_only():
    args = _args(emit_detail(_detail(disabled=True)))
    assert "enable:com.brandon.job" in args
    assert "disable:com.brandon.job" not in args


def test_detail_stdout_actions_present():
    args = _args(emit_detail(_detail()))
    assert "tail-term-out:com.brandon.job" in args
    assert "peek-out:com.brandon.job" in args
    assert "reveal-out:com.brandon.job" in args
    assert "open-plist:com.brandon.job" in args
    assert "copy-label:com.brandon.job" in args


def test_detail_missing_stdout_shows_notice_row():
    out = emit_detail(_detail(stdout_path=None))
    titles = [i["title"] for i in out["items"]]
    args = _args(out)
    assert any("stdout not configured" in t for t in titles)
    assert "peek-out:com.brandon.job" not in args
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_emit_detail.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement** — append to `launchd_monitor.py`:

```python
@dataclass(frozen=True)
class JobDetail:
    """Full detail of a single job, merged from launchctl print and its plist."""

    label: str
    plist_path: "Path | None"
    pid: "int | None"
    last_exit_code: "int | None"
    loaded: bool
    disabled: bool
    stdout_path: "str | None"
    stderr_path: "str | None"
    program_arguments: "list[str]"
    working_dir: "str | None"

    @property
    def state(self) -> JobState:
        """Derive display state; same precedence as JobRecord.state."""
        if self.disabled:
            return JobState.DISABLED
        if not self.loaded:
            return JobState.UNLOADED
        if self.pid is not None:
            return JobState.RUNNING
        if self.last_exit_code:
            return JobState.EXITED
        return JobState.IDLE

    def summary(self) -> str:
        """Build the informational row-0 summary string."""
        state = self.state
        parts = [f"{glyph(state)} {state.value}"]
        if self.pid is not None:
            parts.append(f"PID {self.pid}")
        if self.last_exit_code is not None:
            parts.append(f"last exit {self.last_exit_code}")
        return " · ".join(parts)


def _find_plist(config: Config, label: str) -> "Path | None":
    """Locate a job's plist in the agents dir when launchctl print did not report one."""
    candidate = config.agents_dir / f"{label}.plist"
    return candidate if candidate.exists() else None


def build_detail(config: Config, label: str) -> JobDetail:
    """Gather full detail for a single job, falling back to plist-only when not loaded."""
    uid = os.getuid()
    pinfo = launchctl_print(uid, label)
    loaded = label in launchctl_list()
    disabled = print_disabled(uid).get(label, False)
    plist_path = Path(pinfo.plist_path) if pinfo.plist_path else _find_plist(config, label)
    plist_info: "PlistInfo | None" = None
    if plist_path is not None and plist_path.exists():
        try:
            plist_info = read_plist(plist_path)
        except _PLIST_ERRORS:
            plist_info = None
    stdout_path = (plist_info.stdout_path if plist_info else None) or pinfo.stdout_path
    stderr_path = (plist_info.stderr_path if plist_info else None) or pinfo.stderr_path
    program_arguments = pinfo.program_arguments or (
        plist_info.program_arguments if plist_info else []
    )
    return JobDetail(
        label=label,
        plist_path=plist_path,
        pid=pinfo.pid,
        last_exit_code=pinfo.last_exit_code,
        loaded=loaded,
        disabled=disabled,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        program_arguments=program_arguments,
        working_dir=(plist_info.working_dir if plist_info else None) or pinfo.working_dir,
    )


def _detail_row(title: str, action: str, label: str) -> dict:
    """Build one actionable detail row whose arg is `<action>:<label>`."""
    return {"title": title, "arg": f"{action}:{label}", "valid": True}


def emit_detail(detail: JobDetail) -> dict:
    """Build the Alfred Script Filter payload for a job's action menu."""
    label = detail.label
    items: "list[dict]" = [{"title": detail.summary(), "subtitle": label, "valid": False}]
    items.append(_detail_row("↻ Restart (kickstart -k)", "restart", label))
    if detail.loaded:
        items.append(_detail_row("⏏ Unload (bootout)", "unload", label))
    else:
        items.append(_detail_row("⏵ Load (bootstrap)", "load", label))
    if detail.disabled:
        items.append(_detail_row("✓ Enable", "enable", label))
    else:
        items.append(_detail_row("\U0001f6ab Disable", "disable", label))
    if detail.stdout_path:
        items.append(_detail_row("\U0001f4df Tail stdout (terminal)", "tail-term-out", label))
        items.append(_detail_row("\U0001f441 Peek stdout (Alfred)", "peek-out", label))
        items.append(_detail_row("\U0001f4c2 Reveal stdout in Finder", "reveal-out", label))
        items.append(_detail_row("⧉ Copy stdout path", "copy-logpath-out", label))
    else:
        items.append({"title": "stdout not configured in plist", "valid": False})
    if detail.stderr_path:
        items.append(_detail_row("\U0001f4df Tail stderr (terminal)", "tail-term-err", label))
        items.append(_detail_row("\U0001f441 Peek stderr (Alfred)", "peek-err", label))
    if detail.plist_path is not None:
        items.append(_detail_row("\U0001f4dd Open plist in editor", "open-plist", label))
    items.append(_detail_row("⧉ Copy label", "copy-label", label))
    return {"items": items}


def resolve_path(config: Config, label: str, kind: str) -> str:
    """Return the resolved plist/stdout/stderr path for a label, or '' if unavailable."""
    detail = build_detail(config, label)
    if kind == "plist":
        return str(detail.plist_path) if detail.plist_path else ""
    if kind == "out":
        return detail.stdout_path or ""
    if kind == "err":
        return detail.stderr_path or ""
    return ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_emit_detail.py -v` → PASS. `uv run ruff check .` → clean.

- [ ] **Step 5: Commit**

```bash
git add launchd_monitor.py tests/unit/test_emit_detail.py
git commit -m "feat(launchd-monitor): job detail model and Alfred detail emitter"
```

---

### Task 11: `main()` dispatch + stderr logging

**Files:**
- Modify: `launchd_monitor.py` (append `main`, `__main__` guard, logging setup)
- Create: `tests/unit/test_main.py`

**Interfaces:**
- Consumes: `Config`, `build_records`, `emit_list`, `build_detail`, `emit_detail`, `resolve_path`.
- Produces: `main(argv: list[str]) -> int`. Subcommands:
  - `list [query]` → prints `emit_list(...)` JSON to stdout.
  - `detail <label>` → prints `emit_detail(build_detail(...))` JSON.
  - `path <label> <plist|out|err>` → prints the bare resolved path (no newline formatting beyond a trailing `\n`).
  - Unknown/missing subcommand → logs to stderr, prints an Alfred error item for `list`-family, returns nonzero.

- [ ] **Step 1: Write the failing test** in `tests/unit/test_main.py`

```python
import json

import launchd_monitor as lm
from launchd_monitor import JobDetail, JobRecord, main


def test_main_list(monkeypatch, capsys):
    monkeypatch.setattr(lm, "build_records", lambda cfg, q: [JobRecord("com.a", None, 1, 0, True, False, None, None)])
    rc = main(["list", ""])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["items"][0]["title"] == "com.a"


def test_main_detail(monkeypatch, capsys):
    detail = JobDetail("com.a", None, 1, 0, True, False, None, None, [], None)
    monkeypatch.setattr(lm, "build_detail", lambda cfg, label: detail)
    rc = main(["detail", "com.a"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["items"][0]["subtitle"] == "com.a"


def test_main_path(monkeypatch, capsys):
    monkeypatch.setattr(lm, "resolve_path", lambda cfg, label, kind: "/logs/out.log")
    rc = main(["path", "com.a", "out"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "/logs/out.log"


def test_main_unknown_subcommand_returns_nonzero():
    assert main(["bogus"]) != 0


def test_main_no_args_returns_nonzero():
    assert main([]) != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_main.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement** — append to `launchd_monitor.py` (add `import json`, `import logging`, `import sys` to imports):

```python
import json
import logging
import sys

logging.basicConfig(stream=sys.stderr, level=logging.WARNING, format="launchd-monitor: %(message)s")
_log = logging.getLogger("launchd-monitor")


def main(argv: "list[str]") -> int:
    """Entry point: dispatch list/detail/path subcommands. stdout is Alfred JSON or a path."""
    if not argv:
        _log.error("no subcommand given")
        return 2
    command = argv[0]
    config = Config.from_env(os.environ)
    if command == "list":
        query = argv[1] if len(argv) > 1 else ""
        print(json.dumps(emit_list(build_records(config, query), config)))
        return 0
    if command == "detail":
        if len(argv) < 2:
            _log.error("detail requires a label")
            return 2
        print(json.dumps(emit_detail(build_detail(config, argv[1]))))
        return 0
    if command == "path":
        if len(argv) < 3:
            _log.error("path requires <label> <plist|out|err>")
            return 2
        print(resolve_path(config, argv[1], argv[2]))
        return 0
    _log.error("unknown subcommand: %s", command)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_main.py -v` → PASS. Then full suite + lint:
`uv run pytest -v && uv run ruff check . && uv run ruff format --check .`

- [ ] **Step 5: Manual smoke against real system** (this machine has one real LaunchAgent):

Run: `cd ~/src/alfred-launchd-monitor && python3 launchd_monitor.py list "" | python3 -m json.tool`
Expected: valid JSON with at least one item (e.g. `homebrew.mxcl.postgresql@15`). Then:
`python3 launchd_monitor.py detail homebrew.mxcl.postgresql@15 | python3 -m json.tool` → detail rows.

- [ ] **Step 6: Commit**

```bash
git add launchd_monitor.py tests/unit/test_main.py
git commit -m "feat(launchd-monitor): main() subcommand dispatch"
```

---

### Task 12: `bin/dispatch.sh` action dispatcher

**Files:**
- Create: `bin/dispatch.sh` (chmod +x)
- Create: `tests/unit/test_dispatch.py`

**Interfaces:**
- Consumes: `launchd_monitor.py path <label> <kind>` for path resolution; workflow env vars (`TERMINAL`, `LOG_TOOL`, `LOG_STREAM`, `LOG_LINES`).
- Produces: `bin/dispatch.sh "<action>:<label>"`. Actions: `restart`, `load`, `unload`, `enable`, `disable`, `peek`/`peek-out`/`peek-err`, `tail-term`/`tail-term-out`/`tail-term-err`, `reveal-out`/`reveal-err`, `open-plist`, `copy-label`, `copy-logpath-out`/`copy-logpath-err`. Honors `DISPATCH_DRY_RUN=1` to echo the resolved command (prefixed `+ `) instead of executing — this is the test seam. Peek prints log lines to stdout (→ Alfred Large Type); mutating/terminal actions post an `osascript` notification; failures print to stderr and exit nonzero.

- [ ] **Step 1: Write the failing test** in `tests/unit/test_dispatch.py`

```python
import subprocess
from pathlib import Path

DISPATCH = Path(__file__).parent.parent.parent / "bin" / "dispatch.sh"


def _run(spec, extra_env=None):
    env = {"DISPATCH_DRY_RUN": "1", "PATH": "/usr/bin:/bin", "HOME": "/tmp"}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(DISPATCH), spec],
        capture_output=True,
        text=True,
        env=env,
    )


def test_restart_builds_kickstart():
    out = _run("restart:com.brandon.job").stdout
    assert "/bin/launchctl kickstart -k gui/" in out
    assert "com.brandon.job" in out


def test_unload_builds_bootout():
    assert "/bin/launchctl bootout gui/" in _run("unload:com.brandon.job").stdout


def test_enable_builds_enable():
    assert "/bin/launchctl enable gui/" in _run("enable:com.brandon.job").stdout


def test_disable_builds_disable():
    assert "/bin/launchctl disable gui/" in _run("disable:com.brandon.job").stdout


def test_unknown_action_exits_nonzero():
    result = _run("bogus:com.brandon.job")
    assert result.returncode != 0


def test_label_with_dots_preserved():
    out = _run("restart:com.brandon.some.dotted.label").stdout
    assert "com.brandon.some.dotted.label" in out
```

> The `path`-resolving actions (load/peek/tail/reveal/copy-logpath) shell out to `launchd_monitor.py`, which returns `""` for a nonexistent label — those paths are exercised in the manual verification step, not the dry-run unit tests, to keep the tests hermetic.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_dispatch.py -v`
Expected: FAIL (dispatch.sh does not exist).

- [ ] **Step 3: Implement** — create `bin/dispatch.sh`:

```bash
#!/bin/bash
# Launchd Monitor action dispatcher. Receives "<action>:<label>" and runs a single
# launchctl/open call. Never eval's; passes label + resolved paths as discrete argv.
set -euo pipefail

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin:${PATH:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PY="$SCRIPT_DIR/launchd_monitor.py"
LAUNCHCTL="/bin/launchctl"
DRY="${DISPATCH_DRY_RUN:-0}"
UID_NUM="$(id -u)"
LOG_LINES="${LOG_LINES:-200}"

spec="${1:-}"
action="${spec%%:*}"
label="${spec#*:}"
target="gui/${UID_NUM}/${label}"

run() {
  if [ "$DRY" = "1" ]; then
    echo "+ $*"
  else
    "$@"
  fi
}

notify() {
  [ "$DRY" = "1" ] && { echo "notify: $2"; return 0; }
  osascript -e "display notification \"$2\" with title \"Launchd Monitor\"" >/dev/null 2>&1 || true
}

die() {
  notify "Launchd Monitor" "✗ $1" || true
  echo "$1" >&2
  exit 1
}

resolve() { python3 "$PY" path "$label" "$1"; }

log_tool_cmd() {
  local path="$1"
  case "${LOG_TOOL:-tail}" in
    less) echo "less +F '$path'" ;;
    lnav)
      if command -v lnav >/dev/null 2>&1; then
        echo "lnav '$path'"
      else
        notify "Launchd Monitor" "lnav not installed; using tail"
        echo "tail -n ${LOG_LINES} -F '$path'"
      fi ;;
    *) echo "tail -n ${LOG_LINES} -F '$path'" ;;
  esac
}

open_terminal() {
  local cmd="$1"
  case "${TERMINAL:-ghostty}" in
    ghostty) run open -na Ghostty --args -e "$cmd" ;;
    iterm)   run osascript -e "tell application \"iTerm\" to create window with default profile command \"$cmd\"" ;;
    *)       run osascript -e "tell application \"Terminal\" to do script \"$cmd\"" ;;
  esac
}

peek_stream() {
  local kind="$1" path
  path="$(resolve "$kind")"
  [ -n "$path" ] || { echo "log path not configured ($kind)"; return 0; }
  if [ -f "$path" ]; then
    echo "==> $path <=="
    tail -n "${LOG_LINES}" "$path"
  else
    echo "log not yet created: $path"
  fi
}

tail_stream() {
  local kind="$1" path cmd
  path="$(resolve "$kind")"
  [ -n "$path" ] || die "log path not configured ($kind)"
  cmd="$(log_tool_cmd "$path")"
  open_terminal "$cmd"
  notify "Launchd Monitor" "\U0001f4df Tailing ${kind} for ${label}"
}

case "$action" in
  restart)
    run "$LAUNCHCTL" kickstart -k "$target" && notify "Launchd Monitor" "↻ Restarted ${label}" ;;
  unload)
    run "$LAUNCHCTL" bootout "$target" && notify "Launchd Monitor" "⏏ Unloaded ${label}" ;;
  load)
    plist="$(resolve plist)"
    [ -n "$plist" ] || die "No plist found for ${label}"
    run "$LAUNCHCTL" bootstrap "gui/${UID_NUM}" "$plist" && notify "Launchd Monitor" "⏵ Loaded ${label}" ;;
  enable)
    run "$LAUNCHCTL" enable "$target" && notify "Launchd Monitor" "✓ Enabled ${label}" ;;
  disable)
    run "$LAUNCHCTL" disable "$target" && notify "Launchd Monitor" "\U0001f6ab Disabled ${label}" ;;
  peek)      peek_stream "${LOG_STREAM:-out}" ;;
  peek-out)  peek_stream out ;;
  peek-err)  peek_stream err ;;
  tail-term)     tail_stream "${LOG_STREAM:-out}" ;;
  tail-term-out) tail_stream out ;;
  tail-term-err) tail_stream err ;;
  reveal-out) p="$(resolve out)"; [ -n "$p" ] || die "no stdout path"; run open -R "$p" ;;
  reveal-err) p="$(resolve err)"; [ -n "$p" ] || die "no stderr path"; run open -R "$p" ;;
  open-plist) p="$(resolve plist)"; [ -n "$p" ] || die "no plist path"; run open -t "$p" ;;
  copy-label) [ "$DRY" = "1" ] && echo "+ pbcopy ${label}" || printf '%s' "$label" | pbcopy; notify "Launchd Monitor" "Copied label" ;;
  copy-logpath-out) p="$(resolve out)"; [ "$DRY" = "1" ] && echo "+ pbcopy ${p}" || printf '%s' "$p" | pbcopy ;;
  copy-logpath-err) p="$(resolve err)"; [ "$DRY" = "1" ] && echo "+ pbcopy ${p}" || printf '%s' "$p" | pbcopy ;;
  *) die "Unknown action: ${action}" ;;
esac
```

> The `\uXXXX` sequences above are literal characters to type into the file (the same emoji/glyphs used elsewhere: ↻ ⏏ ⏵ 🚫 ✓ ✗ 📟 👁). They are written as escapes here only to keep the plan copy-pasteable; in the actual file use the real glyph characters.

- [ ] **Step 4: Make executable and run tests**

```bash
chmod +x ~/src/alfred-launchd-monitor/bin/dispatch.sh
cd ~/src/alfred-launchd-monitor && uv run pytest tests/unit/test_dispatch.py -v
```
Expected: PASS. If `shellcheck` is installed, also run `shellcheck bin/dispatch.sh` and address warnings.

- [ ] **Step 5: Manual verification against the real LaunchAgent** (safe, read-only actions):

```bash
cd ~/src/alfred-launchd-monitor
DISPATCH_DRY_RUN=1 bin/dispatch.sh "restart:homebrew.mxcl.postgresql@15"   # shows kickstart command
bin/dispatch.sh "peek-out:homebrew.mxcl.postgresql@15"                     # prints log tail or "not configured"
```
Expected: dry-run prints the `+ /bin/launchctl kickstart -k gui/501/...` line; peek prints log lines or a "not configured"/"not yet created" notice. Do NOT run a real `restart`/`bootout` on postgres unless you intend to.

- [ ] **Step 6: Commit**

```bash
git add bin/dispatch.sh tests/unit/test_dispatch.py
git commit -m "feat(launchd-monitor): dispatch.sh action runner with dry-run seam"
```

---

### Task 13: `tools/build_info_plist.py` — generate the Alfred object graph

> **Deviation from spec (justified):** the spec calls for a hand-authored `info.plist`. Hand-authoring Alfred's UUID-linked connection XML is error-prone and untestable. This task generates it with `plistlib` from named constants so the object graph is reviewable and asserted by tests. Output is byte-identical on each run (deterministic UIDs, no timestamps).

**Files:**
- Create: `tools/build_info_plist.py`
- Create: `tests/unit/test_build_info_plist.py`

**Interfaces:**
- Consumes: nothing at runtime (dev-only; may use Python 3.11 features since it never ships).
- Produces:
  - `build_plist() -> dict` — the full Alfred workflow dict (objects, connections, userconfigurationconfig, metadata).
  - `write_plist(dest: Path) -> None` — writes `build_plist()` to `dest` via `plistlib.dump`.
  - Constants: `UID_LIST`, `UID_DETAIL`, `UID_DISPATCH`, `UID_LARGETYPE` (fixed UUID strings).

- [ ] **Step 1: Write the failing test** in `tests/unit/test_build_info_plist.py`

```python
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "build_info_plist",
    Path(__file__).parent.parent.parent / "tools" / "build_info_plist.py",
)
build_info_plist = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_info_plist)


def test_metadata():
    p = build_info_plist.build_plist()
    assert p["bundleid"] == "com.brandon.launchd-monitor"
    assert p["variablesdontexport"] == []


def test_has_two_script_filters_and_dispatch():
    types = [o["type"] for o in build_info_plist.build_plist()["objects"]]
    assert types.count("alfred.workflow.input.scriptfilter") == 2
    assert "alfred.workflow.action.script" in types
    assert "alfred.workflow.output.largetype" in types


def test_list_keyword_lj():
    objs = {o["uid"]: o for o in build_info_plist.build_plist()["objects"]}
    assert objs[build_info_plist.UID_LIST]["config"]["keyword"] == "lj"


def test_list_connects_to_detail_and_dispatch_with_modifiers():
    conns = build_info_plist.build_plist()["connections"][build_info_plist.UID_LIST]
    dests = {(c["destinationuid"], c["modifiers"]) for c in conns}
    assert (build_info_plist.UID_DETAIL, 0) in dests           # Enter -> detail
    assert (build_info_plist.UID_DISPATCH, 1048576) in dests   # cmd -> dispatch
    assert (build_info_plist.UID_DISPATCH, 524288) in dests    # alt -> dispatch
    assert (build_info_plist.UID_DISPATCH, 262144) in dests    # ctrl -> dispatch


def test_dispatch_connects_to_largetype():
    conns = build_info_plist.build_plist()["connections"][build_info_plist.UID_DISPATCH]
    assert conns[0]["destinationuid"] == build_info_plist.UID_LARGETYPE


def test_config_sheet_variables_present():
    variables = {c["variable"] for c in build_info_plist.build_plist()["userconfigurationconfig"]}
    assert variables == {"SCOPE", "LABEL_GLOB", "AGENTS_DIR", "TERMINAL", "LOG_TOOL", "LOG_STREAM", "LOG_LINES"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_build_info_plist.py -v`
Expected: FAIL (module file missing).

- [ ] **Step 3: Implement** — create `tools/build_info_plist.py`:

```python
"""Generate build/info.plist — the Alfred 5 workflow object graph (dev-only tool)."""

from __future__ import annotations

import plistlib
import sys
from pathlib import Path

UID_LIST = "10000000-0000-0000-0000-000000000001"
UID_DETAIL = "20000000-0000-0000-0000-000000000002"
UID_DISPATCH = "30000000-0000-0000-0000-000000000003"
UID_LARGETYPE = "40000000-0000-0000-0000-000000000004"

# NSEvent modifier flag masks Alfred uses to tag connections.
MOD_NONE = 0
MOD_CMD = 1048576
MOD_ALT = 524288
MOD_CTRL = 262144

_SCRIPT_TYPE_BASH = 0  # /bin/bash
_ARG_AS_ARGV = 1  # "with input as argv" for Run Script; Script Filter reads $1


def _script_filter(uid: str, keyword: str, script: str, with_arg: bool) -> dict:
    """Build a Script Filter object that runs `python3 launchd_monitor.py ...`."""
    return {
        "uid": uid,
        "type": "alfred.workflow.input.scriptfilter",
        "version": 3,
        "config": {
            "alfredfiltersresults": True,
            "argumenttype": 1 if with_arg else 2,
            "keyword": keyword,
            "queuedelaycustom": 3,
            "queuedelayimmediatelyinitially": True,
            "queuedelaymode": 0,
            "runningsubtext": "…",
            "script": script,
            "scriptargtype": 0,  # pass query as argv ($1)
            "scriptfile": "",
            "subtext": "",
            "title": "Launchd Monitor",
            "type": _SCRIPT_TYPE_BASH,
            "withspace": True,
        },
    }


def _dispatch_object() -> dict:
    """Build the Run Script object that invokes bin/dispatch.sh with the item arg."""
    return {
        "uid": UID_DISPATCH,
        "type": "alfred.workflow.action.script",
        "version": 2,
        "config": {
            "concurrently": False,
            "escaping": 0,
            "script": 'bin/dispatch.sh "$1"',
            "scriptargtype": _ARG_AS_ARGV,
            "scriptfile": "",
            "type": _SCRIPT_TYPE_BASH,
        },
    }


def _largetype_object() -> dict:
    """Build the Large Type output object that renders dispatch stdout (peek results)."""
    return {
        "uid": UID_LARGETYPE,
        "type": "alfred.workflow.output.largetype",
        "version": 1,
        "config": {"center": False, "text": "{query}"},
    }


def _conn(dest: str, modifiers: int) -> dict:
    return {
        "destinationuid": dest,
        "modifiers": modifiers,
        "modifiersubtext": "",
        "vitoclose": False,
    }


def _config_var(variable: str, label: str, default: str, kind: str, pairs=None) -> dict:
    """Build one Alfred config-sheet entry (textfield / popupbutton / textfield-int)."""
    config: dict = {"default": default, "placeholder": "", "required": False, "trim": True}
    if kind == "popupbutton":
        config = {"default": default, "pairs": pairs or [], "required": False}
    return {"config": config, "description": "", "label": label, "type": kind, "variable": variable}


def build_plist() -> dict:
    """Assemble the complete Alfred workflow dict."""
    objects = [
        _script_filter(UID_LIST, "lj", 'python3 launchd_monitor.py list "$1"', with_arg=True),
        _script_filter(UID_DETAIL, "", 'python3 launchd_monitor.py detail "$1"', with_arg=True),
        _dispatch_object(),
        _largetype_object(),
    ]
    connections = {
        UID_LIST: [
            _conn(UID_DETAIL, MOD_NONE),
            _conn(UID_DISPATCH, MOD_CMD),
            _conn(UID_DISPATCH, MOD_ALT),
            _conn(UID_DISPATCH, MOD_CTRL),
        ],
        UID_DETAIL: [_conn(UID_DISPATCH, MOD_NONE)],
        UID_DISPATCH: [_conn(UID_LARGETYPE, MOD_NONE)],
    }
    userconfig = [
        _config_var("SCOPE", "Scope", "agents", "popupbutton",
                    pairs=[["LaunchAgents dir", "agents"], ["All gui labels", "gui"]]),
        _config_var("LABEL_GLOB", "Label glob (e.g. com.brandon.*)", "", "textfield"),
        _config_var("AGENTS_DIR", "LaunchAgents dir", "~/Library/LaunchAgents", "textfield"),
        _config_var("TERMINAL", "Terminal", "ghostty", "popupbutton",
                    pairs=[["Ghostty", "ghostty"], ["Terminal", "terminal"], ["iTerm", "iterm"]]),
        _config_var("LOG_TOOL", "Log tool", "tail", "popupbutton",
                    pairs=[["tail", "tail"], ["less", "less"], ["lnav", "lnav"]]),
        _config_var("LOG_STREAM", "Log stream", "out", "popupbutton",
                    pairs=[["stdout", "out"], ["stderr", "err"], ["both", "both"]]),
        _config_var("LOG_LINES", "Log scrollback lines", "200", "textfield"),
    ]
    return {
        "bundleid": "com.brandon.launchd-monitor",
        "category": "Tools",
        "connections": connections,
        "createdby": "brandon.peebles",
        "description": "Observe and control macOS launchd LaunchAgents from Alfred.",
        "disabled": False,
        "name": "Launchd Monitor",
        "objects": objects,
        "readme": "Type `lj` to list launchd jobs. Enter to drill in; ⌘ restart, ⌥ tail, ⌃ peek.",
        "uidata": {
            UID_LIST: {"xpos": 60, "ypos": 60},
            UID_DETAIL: {"xpos": 320, "ypos": 60},
            UID_DISPATCH: {"xpos": 320, "ypos": 220},
            UID_LARGETYPE: {"xpos": 580, "ypos": 220},
        },
        "userconfigurationconfig": userconfig,
        "variablesdontexport": [],
        "version": "0.1.0",
        "webaddress": "",
    }


def write_plist(dest: Path) -> None:
    """Write the workflow dict to dest as an XML plist."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as handle:
        plistlib.dump(build_plist(), handle)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build/info.plist")
    write_plist(out)
    print(f"wrote {out}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_build_info_plist.py -v` → PASS.

- [ ] **Step 5: Generate and lint the plist**

```bash
cd ~/src/alfred-launchd-monitor
python3 tools/build_info_plist.py build/info.plist
plutil -lint build/info.plist
```
Expected: `build/info.plist: OK`.

- [ ] **Step 6: Commit**

```bash
git add tools/build_info_plist.py tests/unit/test_build_info_plist.py
git commit -m "feat(launchd-monitor): generate Alfred info.plist object graph"
```

---

### Task 14: Packaging, README, and end-to-end Alfred verification

**Files:**
- Create: `tools/package.sh` (chmod +x)
- Create: `README.md`
- Create: `icon.png` (placeholder — see Step 2)
- Create: `.gitignore` (ignore `build/`, `*.alfredworkflow`)

**Interfaces:**
- Consumes: `launchd_monitor.py`, `bin/dispatch.sh`, `tools/build_info_plist.py`, `icon.png`.
- Produces: `alfred-launchd-monitor.alfredworkflow` (a zip of the assembled `build/` dir) importable into Alfred.

- [ ] **Step 1: Create `.gitignore`**

```
build/
*.alfredworkflow
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
```

- [ ] **Step 2: Create a placeholder `icon.png`** (icons are optional per spec; emoji glyphs already carry status in text). Any 512×512 PNG works:

```bash
cd ~/src/alfred-launchd-monitor
# macOS built-in: render the SF Symbol / a solid square as a placeholder.
python3 - <<'PY'
import struct, zlib
# Minimal 512x512 opaque dark-teal PNG (placeholder).
w = h = 512
raw = bytearray()
for _y in range(h):
    raw.append(0)  # filter type 0
    raw.extend(b"\x0d\x6e\x6b\xff" * w)  # RGBA
def chunk(tag, data):
    c = tag + data
    return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
png = b"\x89PNG\r\n\x1a\n"
png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
png += chunk(b"IEND", b"")
open("icon.png", "wb").write(png)
print("wrote icon.png")
PY
```

- [ ] **Step 3: Create `tools/package.sh`**

```bash
#!/bin/bash
# Assemble the Alfred bundle into build/ and zip it into alfred-launchd-monitor.alfredworkflow.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build"
OUT="$ROOT/alfred-launchd-monitor.alfredworkflow"

rm -rf "$BUILD" "$OUT"
mkdir -p "$BUILD/bin"

python3 "$ROOT/tools/build_info_plist.py" "$BUILD/info.plist"
plutil -lint "$BUILD/info.plist"

cp "$ROOT/launchd_monitor.py" "$BUILD/launchd_monitor.py"
cp "$ROOT/bin/dispatch.sh" "$BUILD/bin/dispatch.sh"
chmod +x "$BUILD/bin/dispatch.sh"
cp "$ROOT/icon.png" "$BUILD/icon.png"

( cd "$BUILD" && zip -r -X "$OUT" . -x '.*' )
echo "built $OUT"
```

- [ ] **Step 4: Create `README.md`**

````markdown
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
````

- [ ] **Step 5: Build and run the full suite**

```bash
cd ~/src/alfred-launchd-monitor
chmod +x tools/package.sh
uv run pytest -v && uv run ruff check . && uv run ruff format --check .
tools/package.sh
```
Expected: all tests pass, lint clean, `built .../alfred-launchd-monitor.alfredworkflow`.

- [ ] **Step 6: Manual Alfred end-to-end verification** (cannot be automated):

1. `open alfred-launchd-monitor.alfredworkflow` → confirm it imports and the config sheet appears.
2. In Alfred, type `lj` → confirm the real LaunchAgent (`homebrew.mxcl.postgresql@15`) appears with a status glyph.
3. **Enter** on it → confirm the detail action menu shows contextual rows (Unload since it's loaded; Disable since enabled).
4. **⌃ Enter** on the list row (peek) → confirm a Large Type panel shows the log tail or a "not configured/created" notice.
5. Verify each Script Filter's *"with input as"* is **argv** (Alfred → object → "with input as {query}" vs "argv"); the scripts read `$1`. If a filter is set to `{query}` and args break, switch it to argv in the GUI, re-export, and regenerate — note the fix.
6. **Large Type wiring check:** trigger a mutating action (e.g. ⌘ restart) and confirm no empty Large Type box lingers. If an empty box appears, apply the documented fallback: insert a **Conditional** utility after the dispatch object that only routes to Large Type when the arg matches `^peek`; otherwise route to nothing. Record the change in `tools/build_info_plist.py`.

- [ ] **Step 7: Commit**

```bash
git add tools/package.sh README.md \
  icon.png .gitignore
git commit -m "feat(launchd-monitor): packaging script, README, workflow icon"
```

---

## Self-Review

**Spec coverage:**
- List Script Filter (glyphs, status merge, `$1` pre-filter, modifiers) → Tasks 3, 4, 8, 9, 11, 13. ✅
- Detail Script Filter (print+plist merge, contextual rows, action set) → Tasks 6, 10, 13. ✅
- `dispatch.sh` (action:label split, discrete argv, no eval, absolute launchctl, PATH) → Task 12. ✅
- Log-tailing UX (terminal per `TERMINAL`, `LOG_TOOL` map, `tail -F`, `lnav` preflight, peek, `both`) → Task 12. ✅
- Configuration sheet (7 vars + defaults, `variablesdontexport`) → Task 13. ✅
- Error handling (no-match item, print-fails→plist-only, missing log path, action failure notification+nonzero, injection safety, PATH, stale-list) → Tasks 8/9 (no-match), 10 (plist-only fallback + "stdout not configured"), 11 (stderr logging), 12 (notify + `die` nonzero, PATH, discrete argv). Stale-list refresh is handled by the peek/notify feedback + Alfred re-invoking the filter on next open; no auto-refresh object is added (acceptable per spec's "or a toast"). ✅
- Packaging (bundle layout, zip → `.alfredworkflow`, import) → Task 14. ✅
- launchctl command map → covered by dispatch.sh (Task 12) and subprocess wrappers (Task 7). ✅

**Deviations flagged:** (1) `info.plist` generated not hand-authored (Task 13, justified: testability); (2) runtime `str, Enum` not `StrEnum` (Global Constraints, justified: 3.9 runtime); (3) per-row peek routing consolidated onto one dispatch→Large Type path with a documented Conditional fallback (Task 14, Step 6).

**Placeholder scan:** No "TBD"/"add error handling"/"similar to Task N" — every code step is complete. The one hand-adjustment (Alfred GUI argv/Large Type check) is an explicit, unavoidable manual verification, not a code placeholder.

**Type consistency:** `JobRecord`/`JobDetail` field names and the `state`/`subtitle`/`summary` methods are consistent across Tasks 3, 8, 9, 10, 11. `resolve_path(config, label, kind)` (Task 10) matches the `path <label> <kind>` subcommand (Task 11) and `dispatch.sh`'s `resolve()` (Task 12). Action strings emitted in Tasks 9/10 (`restart`, `tail-term`, `peek`, `unload`, `load`, `enable`, `disable`, `tail-term-out`, `peek-out`, `reveal-out`, `open-plist`, `copy-label`, `copy-logpath-out`, `tail-term-err`, `peek-err`) all have matching `case` branches in Task 12. UID/modifier constants in Task 13 match its tests.





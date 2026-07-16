"""Alfred 5 workflow backend: parse launchd/launchctl state and emit Alfred JSON.

Runtime interpreter is macOS system python3 (~3.9); use only the standard library
and no syntax newer than 3.9. stdout is the Alfred interface — diagnostics go to stderr.
"""

from __future__ import annotations

import fnmatch
import os
import plistlib
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


def _parse_int(value: str | None, default: int) -> int:
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
    def from_env(cls, env: Mapping[str, str]) -> Config:
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


def derive_state(
    disabled: bool, loaded: bool, pid: int | None, last_exit_code: int | None
) -> JobState:
    """Derive display state; precedence disabled > unloaded > running > exited > idle."""
    if disabled:
        return JobState.DISABLED
    if not loaded:
        return JobState.UNLOADED
    if pid is not None:
        return JobState.RUNNING
    if last_exit_code:
        return JobState.EXITED
    return JobState.IDLE


@dataclass(frozen=True)
class JobRecord:
    """A launchd job merged from plist source and runtime status, for the list view."""

    label: str
    plist_path: Path | None
    pid: int | None
    last_exit_code: int | None
    loaded: bool
    disabled: bool
    stdout_path: str | None
    stderr_path: str | None

    @property
    def state(self) -> JobState:
        """Derive display state; precedence disabled > unloaded > running > exited > idle."""
        return derive_state(self.disabled, self.loaded, self.pid, self.last_exit_code)

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


_DISABLED_RE = re.compile(r'"(?P<label>[^"]+)"\s*=>\s*(?P<val>true|false)')


@dataclass(frozen=True)
class ListEntry:
    """One row of `launchctl list`: label, current PID (if running), last exit status."""

    label: str
    pid: int | None
    last_status: int


def parse_launchctl_list(output: str) -> dict[str, ListEntry]:
    """Parse `launchctl list` output into label -> ListEntry, skipping the header row."""
    entries: dict[str, ListEntry] = {}
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


def parse_print_disabled(output: str) -> dict[str, bool]:
    """Parse `launchctl print-disabled` output into label -> disabled bool."""
    return {m.group("label"): m.group("val") == "true" for m in _DISABLED_RE.finditer(output)}


@dataclass(frozen=True)
class PlistInfo:
    """Fields read from a LaunchAgent .plist (source of truth for log paths)."""

    label: str | None
    stdout_path: str | None
    stderr_path: str | None
    program_arguments: list[str]
    working_dir: str | None


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


@dataclass(frozen=True)
class PrintInfo:
    """Fields extracted from `launchctl print gui/<uid>/<label>` output."""

    plist_path: str | None
    pid: int | None
    last_exit_code: int | None
    state: str | None
    program_arguments: list[str]
    stdout_path: str | None
    stderr_path: str | None
    working_dir: str | None


def _find_scalar(output: str, key: str) -> str | None:
    """Return the RHS of a `<key> = <value>` line in launchctl print output, or None."""
    match = re.search(rf"^\s*{re.escape(key)}\s*=\s*(.+?)\s*$", output, re.MULTILINE)
    return match.group(1) if match else None


def _find_int(output: str, key: str) -> int | None:
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
    program_arguments: list[str] = []
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


LAUNCHCTL = "/bin/launchctl"
_SAFE_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    """Run a command with an explicit minimal PATH (Alfred's env is minimal)."""
    env = {**os.environ, "PATH": _SAFE_PATH}
    return subprocess.run(args, capture_output=True, text=True, env=env, check=False)


def launchctl_list() -> dict[str, ListEntry]:
    """Return label -> ListEntry from `launchctl list`."""
    return parse_launchctl_list(_run([LAUNCHCTL, "list"]).stdout)


def print_disabled(uid: int) -> dict[str, bool]:
    """Return label -> disabled bool from `launchctl print-disabled gui/<uid>`."""
    return parse_print_disabled(_run([LAUNCHCTL, "print-disabled", f"gui/{uid}"]).stdout)


def launchctl_print(uid: int, label: str) -> PrintInfo:
    """Return parsed detail from `launchctl print gui/<uid>/<label>` (empty if not loaded)."""
    return parse_launchctl_print(_run([LAUNCHCTL, "print", f"gui/{uid}/{label}"]).stdout)


_PLIST_ERRORS = (OSError, plistlib.InvalidFileException, ValueError)


def discover_pairs(
    config: Config, list_entries: dict[str, ListEntry]
) -> list[tuple[str, Path | None]]:
    """Discover (label, plist_path) pairs from the configured scope, filtered by label_glob."""
    pairs: list[tuple[str, Path | None]] = []
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
    plist_path: Path | None,
    list_entries: dict[str, ListEntry],
    disabled_map: dict[str, bool],
    plist_info: PlistInfo | None,
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


def build_records(config: Config, query: str = "") -> list[JobRecord]:
    """Run the full list pipeline: gather runtime status, discover, merge, filter by query."""
    list_entries = launchctl_list()
    disabled_map = print_disabled(os.getuid())
    pairs = discover_pairs(config, list_entries)
    if query:
        needle = query.lower()
        pairs = [(lbl, p) for (lbl, p) in pairs if needle in lbl.lower()]
    records: list[JobRecord] = []
    for label, plist_path in pairs:
        info: PlistInfo | None = None
        if plist_path is not None:
            try:
                info = read_plist(plist_path)
            except _PLIST_ERRORS:
                info = None
        records.append(build_job_record(label, plist_path, list_entries, disabled_map, info))
    return records

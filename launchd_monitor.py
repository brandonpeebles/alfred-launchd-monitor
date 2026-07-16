"""Alfred 5 workflow backend: parse launchd/launchctl state and emit Alfred JSON.

Runtime interpreter is macOS system python3 (~3.9); use only the standard library
and no syntax newer than 3.9. stdout is the Alfred interface — diagnostics go to stderr.
"""

from __future__ import annotations

import fnmatch
import json
import logging
import os
import plistlib
import re
import signal
import subprocess
import sys
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


def _format_exit_status(code: int) -> str:
    """Render an exit code; negative signal-death codes get a readable signal name."""
    if code < 0:
        try:
            return f"killed by {signal.Signals(-code).name}"
        except ValueError:
            pass
    return f"exit {code}"


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
            parts.append(_format_exit_status(self.last_exit_code))
        parts.append("disabled" if self.disabled else ("loaded" if self.loaded else "unloaded"))
        return " · ".join(parts)


_DISABLED_RE = re.compile(r'"(?P<label>[^"]+)"\s*=>\s*(?P<val>true|false|enabled|disabled)')


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
    return {
        m.group("label"): m.group("val") in ("true", "disabled")
        for m in _DISABLED_RE.finditer(output)
    }


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


def emit_list(records: list[JobRecord], config: Config) -> dict:
    """Build the Alfred Script Filter payload for the job list view."""
    if not records:
        pattern = config.label_glob or "*"
        return {
            "items": [
                {
                    "title": f'No launchd jobs match "{pattern}"',
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
                    "alt": {
                        "arg": f"tail-term:{label}",
                        "subtitle": "\U0001f4df Tail log in terminal",
                    },
                    "ctrl": {"arg": f"peek:{label}", "subtitle": "\U0001f441 Peek log in Alfred"},
                },
            }
        )
    return {"items": items}


@dataclass(frozen=True)
class JobDetail:
    """Full detail of a single job, merged from launchctl print and its plist."""

    label: str
    plist_path: Path | None
    pid: int | None
    last_exit_code: int | None
    loaded: bool
    disabled: bool
    stdout_path: str | None
    stderr_path: str | None
    program_arguments: list[str]
    working_dir: str | None

    @property
    def state(self) -> JobState:
        """Derive display state; same precedence as JobRecord.state."""
        return derive_state(self.disabled, self.loaded, self.pid, self.last_exit_code)

    def summary(self) -> str:
        """Build the informational row-0 summary string."""
        state = self.state
        parts = [f"{glyph(state)} {state.value}"]
        if self.pid is not None:
            parts.append(f"PID {self.pid}")
        if self.last_exit_code is not None:
            parts.append(f"last {_format_exit_status(self.last_exit_code)}")
        return " · ".join(parts)


def _find_plist(config: Config, label: str) -> Path | None:
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
    plist_info: PlistInfo | None = None
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
    items: list[dict] = [{"title": detail.summary(), "subtitle": label, "valid": False}]
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


logging.basicConfig(stream=sys.stderr, level=logging.WARNING, format="launchd-monitor: %(message)s")
_log = logging.getLogger("launchd-monitor")


def main(argv: list[str]) -> int:
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

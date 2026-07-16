"""Alfred 5 workflow backend: parse launchd/launchctl state and emit Alfred JSON.

Runtime interpreter is macOS system python3 (~3.9); use only the standard library
and no syntax newer than 3.9. stdout is the Alfred interface — diagnostics go to stderr.
"""

from __future__ import annotations

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

"""Alfred 5 workflow backend: parse launchd/launchctl state and emit Alfred JSON.

Runtime interpreter is macOS system python3 (~3.9); use only the standard library
and no syntax newer than 3.9. stdout is the Alfred interface — diagnostics go to stderr.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
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

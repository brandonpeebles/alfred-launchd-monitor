"""Alfred 5 workflow backend: parse launchd/launchctl state and emit Alfred JSON.

Runtime interpreter is macOS system python3 (~3.9); use only the standard library
and no syntax newer than 3.9. stdout is the Alfred interface — diagnostics go to stderr.
"""

from __future__ import annotations

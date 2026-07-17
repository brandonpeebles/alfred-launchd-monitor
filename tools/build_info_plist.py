"""Generate build/info.plist — the Alfred 5 workflow object graph (dev-only tool)."""

from __future__ import annotations

import plistlib
import sys
from pathlib import Path

import tomllib

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


def _script_filter(
    uid: str, keyword: str, script: str, with_arg: bool, filters_results: bool = True
) -> dict:
    """Build a Script Filter object that runs `python3 launchd_monitor.py ...`.

    filters_results=False when the script emits an already-final menu (the detail
    view): the label arrives as the query, so letting Alfred re-filter rows against
    it would hide every row until the query is cleared.
    """
    return {
        "uid": uid,
        "type": "alfred.workflow.input.scriptfilter",
        "version": 3,
        "config": {
            "alfredfiltersresults": filters_results,
            "argumenttype": 1 if with_arg else 2,
            "keyword": keyword,
            "queuedelaycustom": 3,
            "queuedelayimmediatelyinitially": True,
            "queuedelaymode": 0,
            "runningsubtext": "…",
            "script": script,
            "scriptargtype": _ARG_AS_ARGV if with_arg else 0,  # pass query as argv ($1)
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


def _project_version() -> str:
    """Read `[project].version` from pyproject.toml at the repo root."""
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with pyproject_path.open("rb") as handle:
        data = tomllib.load(handle)
    return data["project"]["version"]


def build_plist() -> dict:
    """Assemble the complete Alfred workflow dict."""
    objects = [
        _script_filter(UID_LIST, "lj", 'python3 launchd_monitor.py list "$1"', with_arg=True),
        _script_filter(
            UID_DETAIL,
            "",
            'python3 launchd_monitor.py detail "$1"',
            with_arg=True,
            filters_results=False,
        ),
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
        _config_var(
            "SCOPE",
            "Scope",
            "agents",
            "popupbutton",
            pairs=[["LaunchAgents dir", "agents"], ["All gui labels", "gui"]],
        ),
        _config_var("LABEL_GLOB", "Label glob (e.g. com.brandon.*)", "", "textfield"),
        _config_var("AGENTS_DIR", "LaunchAgents dir", "~/Library/LaunchAgents", "textfield"),
        _config_var(
            "TERMINAL",
            "Terminal",
            "ghostty",
            "popupbutton",
            pairs=[["Ghostty", "ghostty"], ["Terminal", "terminal"], ["iTerm", "iterm"]],
        ),
        _config_var(
            "LOG_TOOL",
            "Log tool",
            "tail",
            "popupbutton",
            pairs=[["tail", "tail"], ["less", "less"], ["lnav", "lnav"]],
        ),
        _config_var(
            "LOG_STREAM",
            "Log stream",
            "out",
            "popupbutton",
            pairs=[["stdout", "out"], ["stderr", "err"]],
        ),
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
        "version": _project_version(),
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

import dataclasses
import re
from pathlib import Path

from launchd_monitor import Config, JobDetail, JobRecord, emit_detail, emit_list

DISPATCH = Path(__file__).parent.parent.parent / "bin" / "dispatch.sh"

LABEL = "com.brandon.contract"

# bin/dispatch.sh handles these actions, but nothing in launchd_monitor.py ever
# emits them -- tracked separately as issue #11 ("Asymmetric stderr actions:
# reveal-err/copy-logpath-err handled in dispatch but never emitted"). Issue #11
# is resolved: launchd_monitor.py now emits both, so this allowlist is empty.
KNOWN_DISPATCH_ONLY_GAPS = set()


_DEFAULT_DETAIL = JobDetail(
    label=LABEL,
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


def _detail(**kw):
    return dataclasses.replace(_DEFAULT_DETAIL, **kw)


def _actions_from_args(args):
    suffix = f":{LABEL}"
    actions = set()
    for arg in args:
        if isinstance(arg, str) and arg.endswith(suffix):
            actions.add(arg[: -len(suffix)])
    return actions


def _emitted_actions():
    """Union of every action string the Python emitter can produce."""
    args = []

    rec = JobRecord(LABEL, None, 4821, 0, True, False, None, None)
    list_out = emit_list([rec], Config.from_env({}))
    for item in list_out["items"]:
        args.append(item.get("arg"))
        for mod in item.get("mods", {}).values():
            args.append(mod.get("arg"))

    for detail in (
        _detail(loaded=True, disabled=False),
        _detail(loaded=False, pid=None, disabled=True),
    ):
        detail_out = emit_detail(detail)
        for item in detail_out["items"]:
            args.append(item.get("arg"))
            for mod in item.get("mods", {}).values():
                args.append(mod.get("arg"))

    return _actions_from_args(args)


def _dispatch_case_labels():
    """Case labels handled by bin/dispatch.sh's `case "$action" in ... esac` block."""
    text = DISPATCH.read_text()
    match = re.search(r'case "\$action" in(.*?)esac', text, re.DOTALL)
    assert match is not None
    block = match.group(1)
    labels = set()
    for line in block.splitlines():
        m = re.match(r"^\s*([a-zA-Z][a-zA-Z0-9_-]*)\)", line)
        if m:
            for label in m.group(1).split("|"):
                labels.add(label)
    return labels


def test_every_emitted_action_has_a_dispatch_branch():
    assert _emitted_actions() - _dispatch_case_labels() == set()


def test_dispatch_branches_are_all_emitted_or_documented_gaps():
    dead = _dispatch_case_labels() - _emitted_actions() - KNOWN_DISPATCH_ONLY_GAPS
    assert dead == set()


def test_known_gaps_allowlist_is_still_accurate():
    # This assertion starts failing the day issue #11 closes (either by emitting
    # these actions or deleting the dispatch branches) -- that failure is the
    # intended signal to shrink/remove KNOWN_DISPATCH_ONLY_GAPS.
    assert (_dispatch_case_labels() - _emitted_actions()) >= KNOWN_DISPATCH_ONLY_GAPS

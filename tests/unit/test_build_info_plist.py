import importlib.util
from pathlib import Path

import tomllib  # ty: ignore[unresolved-import]

_spec = importlib.util.spec_from_file_location(
    "build_info_plist",
    Path(__file__).parent.parent.parent / "tools" / "build_info_plist.py",
)
assert _spec is not None and _spec.loader is not None
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
    assert (build_info_plist.UID_DETAIL, 0) in dests  # Enter -> detail
    assert (build_info_plist.UID_DISPATCH, 1048576) in dests  # cmd -> dispatch
    assert (build_info_plist.UID_DISPATCH, 524288) in dests  # alt -> dispatch
    assert (build_info_plist.UID_DISPATCH, 262144) in dests  # ctrl -> dispatch


def test_dispatch_connects_to_largetype():
    conns = build_info_plist.build_plist()["connections"][build_info_plist.UID_DISPATCH]
    assert conns[0]["destinationuid"] == build_info_plist.UID_LARGETYPE


def test_config_sheet_variables_present():
    cfg = build_info_plist.build_plist()["userconfigurationconfig"]
    variables = {c["variable"] for c in cfg}
    expected = {
        "SCOPE",
        "LABEL_GLOB",
        "AGENTS_DIR",
        "TERMINAL",
        "LOG_TOOL",
        "LOG_STREAM",
        "LOG_LINES",
    }
    assert variables == expected


def test_script_filters_use_argv():
    objs = {o["uid"]: o for o in build_info_plist.build_plist()["objects"]}
    assert (
        objs[build_info_plist.UID_LIST]["config"]["scriptargtype"] == build_info_plist._ARG_AS_ARGV
    )
    assert (
        objs[build_info_plist.UID_DETAIL]["config"]["scriptargtype"]
        == build_info_plist._ARG_AS_ARGV
    )


def test_detail_filter_does_not_let_alfred_refilter_results():
    # The detail Script Filter receives the selected label as its query. Its script
    # emits the exact action menu, so Alfred must NOT re-filter those rows against
    # the label — doing so hides every row until the query is cleared.
    objs = {o["uid"]: o for o in build_info_plist.build_plist()["objects"]}
    assert objs[build_info_plist.UID_DETAIL]["config"]["alfredfiltersresults"] is False


def test_log_stream_popup_has_no_both_option():
    cfg = build_info_plist.build_plist()["userconfigurationconfig"]
    log_stream_var = next(c for c in cfg if c["variable"] == "LOG_STREAM")
    values = [pair[1] for pair in log_stream_var["config"]["pairs"]]
    assert values == ["out", "err"]


def test_version_matches_pyproject_toml():
    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    with pyproject_path.open("rb") as handle:
        data = tomllib.load(handle)
    assert build_info_plist.build_plist()["version"] == data["project"]["version"]

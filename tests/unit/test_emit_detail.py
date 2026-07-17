import dataclasses
from pathlib import Path

from launchd_monitor import JobDetail, emit_detail

_DEFAULT_DETAIL = JobDetail(
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


def _detail(**kw):
    return dataclasses.replace(_DEFAULT_DETAIL, **kw)


def _args(out):
    return [i.get("arg") for i in out["items"]]


def _item(out, arg):
    return next(i for i in out["items"] if i.get("arg") == arg)


def test_detail_summary_row_first_and_invalid():
    out = emit_detail(_detail())
    assert out["items"][0]["valid"] is False
    assert out["items"][0]["title"].startswith("🟢 running")


def test_detail_summary_disabled_with_pid_shows_running():
    out = emit_detail(_detail(disabled=True))
    title = out["items"][0]["title"]
    assert "disabled (running, PID 4821)" in title


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


def test_detail_running_shows_stop():
    args = _args(emit_detail(_detail(loaded=True, pid=4821)))
    assert "stop:com.brandon.job" in args


def test_detail_not_running_hides_stop():
    args = _args(emit_detail(_detail(loaded=False, pid=None)))
    assert "stop:com.brandon.job" not in args


def test_detail_missing_stdout_shows_notice_row():
    out = emit_detail(_detail(stdout_path=None))
    titles = [i["title"] for i in out["items"]]
    args = _args(out)
    assert any("stdout not configured" in t for t in titles)
    assert "peek-out:com.brandon.job" not in args


def test_detail_summary_signal_terminated():
    assert "SIGTERM" in _detail(last_exit_code=-15, pid=None).summary()


def test_detail_stderr_actions_present():
    args = _args(emit_detail(_detail()))
    assert "tail-term-err:com.brandon.job" in args
    assert "peek-err:com.brandon.job" in args
    assert "reveal-err:com.brandon.job" in args
    assert "copy-logpath-err:com.brandon.job" in args


def test_detail_missing_stderr_omits_actions():
    args = _args(emit_detail(_detail(stderr_path=None)))
    assert "reveal-err:com.brandon.job" not in args
    assert "copy-logpath-err:com.brandon.job" not in args


def test_detail_stdout_rows_have_subtitle_and_quicklookurl():
    out = emit_detail(_detail(stdout_path="/logs/out.log"))
    for arg in (
        "peek-out:com.brandon.job",
        "tail-term-out:com.brandon.job",
        "reveal-out:com.brandon.job",
        "copy-logpath-out:com.brandon.job",
    ):
        item = _item(out, arg)
        assert item["subtitle"] == "/logs/out.log"
        assert item["quicklookurl"] == "/logs/out.log"


def test_detail_stderr_rows_have_subtitle_and_quicklookurl():
    out = emit_detail(_detail(stderr_path="/logs/err.log"))
    for arg in (
        "tail-term-err:com.brandon.job",
        "peek-err:com.brandon.job",
        "reveal-err:com.brandon.job",
        "copy-logpath-err:com.brandon.job",
    ):
        item = _item(out, arg)
        assert item["subtitle"] == "/logs/err.log"
        assert item["quicklookurl"] == "/logs/err.log"


def test_detail_plist_row_has_subtitle_and_quicklookurl():
    out = emit_detail(_detail())
    item = _item(out, "open-plist:com.brandon.job")
    assert item["subtitle"] == "/x.plist"
    assert item["quicklookurl"] == "/x.plist"


def test_detail_pathless_rows_unaffected():
    out = emit_detail(_detail())
    item = _item(out, "restart:com.brandon.job")
    assert "quicklookurl" not in item
    assert "subtitle" not in item

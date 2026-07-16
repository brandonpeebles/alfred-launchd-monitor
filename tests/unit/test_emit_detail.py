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

from launchd_monitor import JobRecord, JobState, glyph


def _rec(**kw):
    base = dict(
        label="com.brandon.job",
        plist_path=None,
        pid=None,
        last_exit_code=0,
        loaded=True,
        disabled=False,
        stdout_path=None,
        stderr_path=None,
    )
    base.update(kw)
    return JobRecord(**base)


def test_state_precedence():
    assert _rec(disabled=True, loaded=False).state is JobState.DISABLED
    assert _rec(loaded=False).state is JobState.UNLOADED
    assert _rec(pid=4821).state is JobState.RUNNING
    assert _rec(pid=None, last_exit_code=78).state is JobState.EXITED
    assert _rec(pid=None, last_exit_code=0).state is JobState.IDLE


def test_glyphs():
    assert glyph(JobState.RUNNING) == "🟢"
    assert glyph(JobState.IDLE) == "⚪"
    assert glyph(JobState.EXITED) == "🔴"
    assert glyph(JobState.UNLOADED) == "⚫"
    assert glyph(JobState.DISABLED) == "🚫"


def test_subtitle():
    sub = _rec(pid=4821, last_exit_code=0).subtitle()
    assert sub == "🟢 running · PID 4821 · exit 0 · loaded"
    assert _rec(pid=None, last_exit_code=78).subtitle() == "🔴 exited · exit 78 · loaded"
    assert _rec(loaded=False, last_exit_code=None).subtitle() == "⚫ unloaded · unloaded"


def test_subtitle_signal_terminated():
    assert "SIGTERM" in _rec(pid=None, last_exit_code=-15).subtitle()


def test_subtitle_unknown_signal_falls_back_to_number():
    assert "-999" in _rec(pid=None, last_exit_code=-999).subtitle()


def test_subtitle_disabled_with_pid_shows_running():
    assert (
        _rec(disabled=True, pid=4821, last_exit_code=0).subtitle()
        == "🚫 disabled (running, PID 4821) · exit 0 · disabled"
    )

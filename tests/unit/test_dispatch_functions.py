import subprocess
from pathlib import Path

DISPATCH = Path(__file__).parent.parent.parent / "bin" / "dispatch.sh"


def _source_run(snippet, extra_env=None):
    env = {
        "DISPATCH_SOURCE_ONLY": "1",
        "PATH": "/usr/bin:/bin",
        "HOME": "/tmp",
    }
    if extra_env:
        env.update(extra_env)
    script = f'source "{DISPATCH}"\n{snippet}\n'
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env=env,
    )


def test_log_tool_cmd_default_is_tail():
    result = _source_run(
        'log_tool_cmd "$TEST_PATH"',
        {"TEST_PATH": "/tmp/x.log"},
    )
    assert result.stdout.strip() == "tail -n 200 -F '/tmp/x.log'"


def test_log_tool_cmd_less():
    result = _source_run(
        'log_tool_cmd "$TEST_PATH"',
        {"TEST_PATH": "/tmp/x.log", "LOG_TOOL": "less"},
    )
    assert result.stdout.strip() == "less +F '/tmp/x.log'"


def test_log_tool_cmd_lnav_present(tmp_path):
    lnav_stub = tmp_path / "lnav"
    lnav_stub.write_text("#!/bin/sh\n")
    lnav_stub.chmod(0o755)
    result = _source_run(
        'log_tool_cmd "$TEST_PATH"',
        {
            "TEST_PATH": "/tmp/x.log",
            "LOG_TOOL": "lnav",
            "PATH": f"{tmp_path}:/usr/bin:/bin",
        },
    )
    assert result.stdout.strip() == "lnav '/tmp/x.log'"


def test_log_tool_cmd_lnav_absent_falls_back_to_tail():
    result = _source_run(
        'log_tool_cmd "$TEST_PATH"',
        {
            "TEST_PATH": "/tmp/x.log",
            "LOG_TOOL": "lnav",
            "DISPATCH_DRY_RUN": "1",
        },
    )
    lines = result.stdout.strip().splitlines()
    assert lines[0] == "notify: lnav not installed; using tail"
    assert lines[1] == "tail -n 200 -F '/tmp/x.log'"


def test_log_tool_cmd_quotes_space_and_apostrophe():
    result = _source_run(
        'log_tool_cmd "$TEST_PATH"',
        {"TEST_PATH": "/Users/brandon/Library/Logs/joe's job.log"},
    )
    out = result.stdout.strip()
    assert "joe" in out
    assert "job.log" in out
    assert "'\\''" in out


def test_open_terminal_ghostty_dry_run():
    result = _source_run(
        'open_terminal "tail -n 200 -F /tmp/x.log"',
        {"DISPATCH_DRY_RUN": "1", "TERMINAL": "ghostty"},
    )
    out = result.stdout.strip()
    assert out.startswith("+ open -na Ghostty --args -e /bin/sh -c")
    assert "tail -n 200 -F /tmp/x.log" in out


def test_open_terminal_iterm_dry_run():
    result = _source_run(
        'open_terminal "tail -n 200 -F /tmp/x.log"',
        {"DISPATCH_DRY_RUN": "1", "TERMINAL": "iterm"},
    )
    out = result.stdout.strip()
    assert out.startswith("+ osascript -")
    assert "tail -n 200 -F /tmp/x.log" in out


def test_open_terminal_default_terminal_dry_run():
    result = _source_run(
        'open_terminal "tail -n 200 -F /tmp/x.log"',
        {"DISPATCH_DRY_RUN": "1", "TERMINAL": "terminal"},
    )
    out = result.stdout.strip()
    assert out.startswith("+ osascript -")
    assert "tail -n 200 -F /tmp/x.log" in out

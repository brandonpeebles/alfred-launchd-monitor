import subprocess
from pathlib import Path

DISPATCH = Path(__file__).parent.parent.parent / "bin" / "dispatch.sh"


def _run(spec, extra_env=None):
    env = {"DISPATCH_DRY_RUN": "1", "PATH": "/usr/bin:/bin", "HOME": "/tmp"}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(DISPATCH), spec],
        capture_output=True,
        text=True,
        env=env,
    )


def test_restart_builds_kickstart():
    out = _run("restart:com.brandon.job").stdout
    assert "/bin/launchctl kickstart -k gui/" in out
    assert "com.brandon.job" in out


def test_unload_builds_bootout():
    assert "/bin/launchctl bootout gui/" in _run("unload:com.brandon.job").stdout


def test_enable_builds_enable():
    assert "/bin/launchctl enable gui/" in _run("enable:com.brandon.job").stdout


def test_disable_builds_disable():
    assert "/bin/launchctl disable gui/" in _run("disable:com.brandon.job").stdout


def test_unknown_action_exits_nonzero():
    result = _run("bogus:com.brandon.job")
    assert result.returncode != 0


def test_label_with_dots_preserved():
    out = _run("restart:com.brandon.some.dotted.label").stdout
    assert "com.brandon.some.dotted.label" in out


def test_copy_label_dry_run():
    result = _run("copy-label:com.brandon.job")
    assert result.returncode == 0
    assert "+ pbcopy com.brandon.job" in result.stdout


def _write_stub_launchd_monitor(tmp_path):
    stub = tmp_path / "stub_launchd_monitor.py"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        'if len(sys.argv) >= 2 and sys.argv[1] == "path":\n'
        '    print(os.environ.get("FAKE_PATH", ""))\n'
    )
    stub.chmod(0o755)
    return stub


def test_copy_logpath_missing_path_exits_nonzero(tmp_path):
    # Hermetic: point PY at a stub that never shells out to launchctl, so this
    # doesn't depend on the real launchd state of whatever machine runs the suite.
    stub = _write_stub_launchd_monitor(tmp_path)
    result = _run(
        "copy-logpath-out:com.brandon.definitely-not-a-real-label",
        extra_env={"PY": str(stub)},
    )
    assert result.returncode != 0


def test_copy_logpath_out_uses_resolved_path(tmp_path):
    stub = _write_stub_launchd_monitor(tmp_path)
    result = _run(
        "copy-logpath-out:com.brandon.job",
        extra_env={"PY": str(stub), "FAKE_PATH": "/tmp/some/job/out.log"},
    )
    assert result.returncode == 0
    assert "+ pbcopy /tmp/some/job/out.log" in result.stdout


def test_restart_failure_notifies_and_exits_nonzero(tmp_path):
    # Drive the failure path hermetically: point LAUNCHCTL at /usr/bin/false so the
    # mutation fails deterministically (no real launchctl side effects), and stub
    # osascript via the OSASCRIPT seam so notify() is captured instead of popping a
    # real macOS notification. Under set -euo pipefail a failed launchctl must reach
    # `|| die`, which notifies (✗ …) and exits nonzero -- not abort silently.
    notify_log = tmp_path / "notify.log"
    stub_osascript = tmp_path / "osascript_stub.sh"
    stub_osascript.write_text('#!/bin/sh\nprintf "%s\\n" "$2" >> "$NOTIFY_LOG"\n')
    stub_osascript.chmod(0o755)

    result = _run(
        "restart:com.brandon.definitely-not-a-real-label-nonexistent",
        extra_env={
            "DISPATCH_DRY_RUN": "0",
            "LAUNCHCTL": "/usr/bin/false",
            "OSASCRIPT": str(stub_osascript),
            "NOTIFY_LOG": str(notify_log),
        },
    )

    assert result.returncode != 0
    assert "restart failed" in result.stderr
    assert notify_log.exists()
    assert "✗ restart failed" in notify_log.read_text()

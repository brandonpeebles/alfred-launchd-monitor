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


def test_copy_logpath_missing_path_exits_nonzero():
    result = _run("copy-logpath-out:com.brandon.definitely-not-a-real-label")
    assert result.returncode != 0

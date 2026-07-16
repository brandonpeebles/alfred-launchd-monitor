import subprocess

import launchd_monitor as lm


def _fake_completed(stdout):
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def test_launchctl_list_uses_boundary(monkeypatch):
    calls = {}

    def fake_run(args, **kwargs):
        calls["args"] = args
        calls["path"] = kwargs["env"]["PATH"]
        return _fake_completed("PID\tStatus\tLabel\n4821\t0\tcom.brandon.running-job\n")

    monkeypatch.setattr(lm.subprocess, "run", fake_run)
    entries = lm.launchctl_list()
    assert calls["args"] == ["/bin/launchctl", "list"]
    assert calls["path"] == "/usr/bin:/bin:/usr/sbin:/sbin"
    assert entries["com.brandon.running-job"].pid == 4821


def test_launchctl_print_builds_target(monkeypatch):
    seen = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        return _fake_completed("com.brandon.running-job = {\n\tpid = 4821\n}\n")

    monkeypatch.setattr(lm.subprocess, "run", fake_run)
    info = lm.launchctl_print(501, "com.brandon.running-job")
    assert seen["args"] == ["/bin/launchctl", "print", "gui/501/com.brandon.running-job"]
    assert info.pid == 4821


def test_print_disabled_builds_target(monkeypatch):
    seen = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        return _fake_completed('disabled services = {\n\t"com.brandon.x" => true\n}\n')

    monkeypatch.setattr(lm.subprocess, "run", fake_run)
    disabled = lm.print_disabled(501)
    assert seen["args"] == ["/bin/launchctl", "print-disabled", "gui/501"]
    assert disabled == {"com.brandon.x": True}

import json

import launchd_monitor as lm
from launchd_monitor import JobDetail, JobRecord, main


def test_main_list(monkeypatch, capsys):
    record = JobRecord("com.a", None, 1, 0, True, False, None, None)
    monkeypatch.setattr(lm, "build_records", lambda cfg, q: [record])
    rc = main(["list", ""])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["items"][0]["title"] == "com.a"


def test_main_detail(monkeypatch, capsys):
    detail = JobDetail("com.a", None, 1, 0, True, False, None, None, [], None)
    monkeypatch.setattr(lm, "build_detail", lambda cfg, label: detail)
    rc = main(["detail", "com.a"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["items"][0]["subtitle"] == "com.a"


def test_main_path(monkeypatch, capsys):
    monkeypatch.setattr(lm, "resolve_path", lambda cfg, label, kind: "/logs/out.log")
    rc = main(["path", "com.a", "out"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "/logs/out.log"


def test_main_unknown_subcommand_returns_nonzero():
    assert main(["bogus"]) != 0


def test_main_no_args_returns_nonzero():
    assert main([]) != 0

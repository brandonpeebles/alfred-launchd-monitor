from pathlib import Path

import launchd_monitor as lm
from launchd_monitor import Config, JobDetail, resolve_path


def _detail(**kw):
    base = dict(
        label="com.a",
        plist_path=Path("/x.plist"),
        pid=None,
        last_exit_code=None,
        loaded=True,
        disabled=False,
        stdout_path="/logs/out.log",
        stderr_path="/logs/err.log",
        program_arguments=[],
        working_dir=None,
    )
    base.update(kw)
    return JobDetail(**base)


def test_resolve_path_plist_present(monkeypatch):
    detail = _detail(plist_path=Path("/x.plist"))
    monkeypatch.setattr(lm, "build_detail", lambda cfg, label: detail)
    cfg = Config.from_env({})
    assert resolve_path(cfg, "com.a", "plist") == "/x.plist"


def test_resolve_path_plist_absent(monkeypatch):
    detail = _detail(plist_path=None)
    monkeypatch.setattr(lm, "build_detail", lambda cfg, label: detail)
    cfg = Config.from_env({})
    assert resolve_path(cfg, "com.a", "plist") == ""


def test_resolve_path_out_present(monkeypatch):
    detail = _detail(stdout_path="/logs/out.log")
    monkeypatch.setattr(lm, "build_detail", lambda cfg, label: detail)
    cfg = Config.from_env({})
    assert resolve_path(cfg, "com.a", "out") == "/logs/out.log"


def test_resolve_path_out_absent(monkeypatch):
    detail = _detail(stdout_path=None)
    monkeypatch.setattr(lm, "build_detail", lambda cfg, label: detail)
    cfg = Config.from_env({})
    assert resolve_path(cfg, "com.a", "out") == ""


def test_resolve_path_err_present(monkeypatch):
    detail = _detail(stderr_path="/logs/err.log")
    monkeypatch.setattr(lm, "build_detail", lambda cfg, label: detail)
    cfg = Config.from_env({})
    assert resolve_path(cfg, "com.a", "err") == "/logs/err.log"


def test_resolve_path_err_absent(monkeypatch):
    detail = _detail(stderr_path=None)
    monkeypatch.setattr(lm, "build_detail", lambda cfg, label: detail)
    cfg = Config.from_env({})
    assert resolve_path(cfg, "com.a", "err") == ""


def test_resolve_path_unrecognized_kind_returns_empty(monkeypatch):
    detail = _detail()
    monkeypatch.setattr(lm, "build_detail", lambda cfg, label: detail)
    cfg = Config.from_env({})
    assert resolve_path(cfg, "com.a", "bogus") == ""

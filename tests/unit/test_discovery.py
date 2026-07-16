from pathlib import Path

import launchd_monitor as lm
from launchd_monitor import Config, ListEntry, PlistInfo, build_job_record, discover_pairs


def test_discover_pairs_gui_scope():
    cfg = Config.from_env({"SCOPE": "gui"})
    entries = {"com.a": ListEntry("com.a", None, 0), "com.b": ListEntry("com.b", 1, 0)}
    pairs = discover_pairs(cfg, entries)
    assert pairs == [("com.a", None), ("com.b", None)]


def test_discover_pairs_gui_scope_glob_filter():
    cfg = Config.from_env({"SCOPE": "gui", "LABEL_GLOB": "com.brandon.*"})
    entries = {
        "com.brandon.x": ListEntry("com.brandon.x", None, 0),
        "com.apple.y": ListEntry("com.apple.y", None, 0),
    }
    assert discover_pairs(cfg, entries) == [("com.brandon.x", None)]


def test_discover_pairs_agents_scope(tmp_path, monkeypatch):
    plist = tmp_path / "com.brandon.job.plist"
    plist.write_bytes(b"")  # content irrelevant; read_plist is stubbed
    monkeypatch.setattr(
        lm, "read_plist", lambda p: PlistInfo("com.brandon.job", None, None, [], None)
    )
    cfg = Config.from_env({"SCOPE": "agents", "AGENTS_DIR": str(tmp_path)})
    assert discover_pairs(cfg, {}) == [("com.brandon.job", plist)]


def test_discover_pairs_agents_scope_skips_unreadable(tmp_path, monkeypatch):
    (tmp_path / "bad.plist").write_bytes(b"")

    def boom(_p):
        raise ValueError("corrupt")

    monkeypatch.setattr(lm, "read_plist", boom)
    cfg = Config.from_env({"SCOPE": "agents", "AGENTS_DIR": str(tmp_path)})
    assert discover_pairs(cfg, {}) == []


def test_build_job_record_running():
    entries = {"com.a": ListEntry("com.a", 4821, 0)}
    rec = build_job_record("com.a", Path("/x.plist"), entries, {}, None)
    assert rec.loaded is True
    assert rec.pid == 4821
    assert rec.state.value == "running"


def test_build_job_record_unloaded_disabled():
    rec = build_job_record("com.a", None, {}, {"com.a": True}, None)
    assert rec.loaded is False
    assert rec.disabled is True
    assert rec.state.value == "disabled"

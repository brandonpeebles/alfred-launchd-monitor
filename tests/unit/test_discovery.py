from pathlib import Path

import launchd_monitor as lm
from launchd_monitor import Config, ListEntry, PlistInfo, build_job_record, discover_pairs

_EMPTY_PRINT_INFO = lm.PrintInfo(
    plist_path=None,
    pid=None,
    last_exit_code=None,
    state=None,
    program_arguments=[],
    stdout_path=None,
    stderr_path=None,
    working_dir=None,
)


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


def test_find_plist_exact_filename_match(tmp_path, monkeypatch):
    plist = tmp_path / "com.x.y.plist"
    plist.write_bytes(b"")
    monkeypatch.setattr(lm, "read_plist", lambda p: PlistInfo("com.x.y", None, None, [], None))
    cfg = Config.from_env({"SCOPE": "agents", "AGENTS_DIR": str(tmp_path)})
    assert lm._find_plist(cfg, "com.x.y") == plist


def test_find_plist_scans_for_mismatched_label(tmp_path, monkeypatch):
    plist = tmp_path / "myjob.plist"
    plist.write_bytes(b"")

    def fake_read_plist(path):
        assert path == plist
        return PlistInfo("com.x.y", None, None, [], None)

    monkeypatch.setattr(lm, "read_plist", fake_read_plist)
    cfg = Config.from_env({"SCOPE": "agents", "AGENTS_DIR": str(tmp_path)})
    assert lm._find_plist(cfg, "com.x.y") == plist


def test_find_plist_no_match_returns_none(tmp_path, monkeypatch):
    (tmp_path / "other.plist").write_bytes(b"")
    monkeypatch.setattr(lm, "read_plist", lambda p: PlistInfo("com.other", None, None, [], None))
    cfg = Config.from_env({"SCOPE": "agents", "AGENTS_DIR": str(tmp_path)})
    assert lm._find_plist(cfg, "com.x.y") is None


def test_build_detail_finds_plist_by_label_when_unloaded(tmp_path, monkeypatch):
    plist = tmp_path / "myjob.plist"
    plist.write_bytes(b"")
    plist_info = PlistInfo("com.x.y", "/tmp/out.log", "/tmp/err.log", ["/usr/bin/foo"], "/tmp")
    monkeypatch.setattr(lm, "read_plist", lambda p: plist_info)
    monkeypatch.setattr(lm, "launchctl_print", lambda uid, label: _EMPTY_PRINT_INFO)
    monkeypatch.setattr(lm, "launchctl_list", lambda: {})
    monkeypatch.setattr(lm, "print_disabled", lambda uid: {})
    cfg = Config.from_env({"SCOPE": "agents", "AGENTS_DIR": str(tmp_path)})

    detail = lm.build_detail(cfg, "com.x.y")

    assert detail.plist_path == plist
    assert detail.stdout_path == "/tmp/out.log"
    assert detail.stderr_path == "/tmp/err.log"
    assert detail.program_arguments == ["/usr/bin/foo"]
    assert detail.working_dir == "/tmp"

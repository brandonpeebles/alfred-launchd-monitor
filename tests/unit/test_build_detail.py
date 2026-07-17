import dataclasses

import launchd_monitor as lm
from launchd_monitor import Config, ListEntry, PlistInfo, PrintInfo, build_detail

_DEFAULT_PRINT_INFO = PrintInfo(
    plist_path=None,
    pid=None,
    last_exit_code=None,
    state=None,
    program_arguments=[],
    stdout_path=None,
    stderr_path=None,
    working_dir=None,
)


def _pinfo(**overrides):
    return dataclasses.replace(_DEFAULT_PRINT_INFO, **overrides)


_DEFAULT_PLIST_INFO = PlistInfo(
    label="com.a",
    stdout_path=None,
    stderr_path=None,
    program_arguments=[],
    working_dir=None,
)


def _plist_info(**overrides):
    return dataclasses.replace(_DEFAULT_PLIST_INFO, **overrides)


def _patch_common(monkeypatch, pinfo, plist_info=None, loaded=False, disabled=False):
    monkeypatch.setattr(lm, "launchctl_print", lambda uid, label: pinfo)
    monkeypatch.setattr(
        lm, "launchctl_list", lambda: ({"com.a": ListEntry("com.a", None, 0)} if loaded else {})
    )
    monkeypatch.setattr(
        lm, "print_disabled", lambda uid: ({"com.a": True} if disabled else {})
    )
    if plist_info is not None:
        monkeypatch.setattr(lm, "read_plist", lambda path: plist_info)
    else:
        def boom(path):
            raise AssertionError("read_plist should not be called")

        monkeypatch.setattr(lm, "read_plist", boom)


def test_stdout_stderr_plist_wins_when_both_present(tmp_path, monkeypatch):
    plist_path = tmp_path / "com.a.plist"
    plist_path.write_bytes(b"")
    pinfo = _pinfo(
        plist_path=str(plist_path), stdout_path="/print/out.log", stderr_path="/print/err.log"
    )
    plist_info = _plist_info(stdout_path="/plist/out.log", stderr_path="/plist/err.log")
    _patch_common(monkeypatch, pinfo, plist_info=plist_info)
    cfg = Config.from_env({"AGENTS_DIR": str(tmp_path)})

    detail = build_detail(cfg, "com.a")

    assert detail.stdout_path == "/plist/out.log"
    assert detail.stderr_path == "/plist/err.log"


def test_stdout_stderr_falls_back_to_print_when_plist_has_no_path(tmp_path, monkeypatch):
    plist_path = tmp_path / "com.a.plist"
    plist_path.write_bytes(b"")
    pinfo = _pinfo(
        plist_path=str(plist_path), stdout_path="/print/out.log", stderr_path="/print/err.log"
    )
    plist_info = _plist_info(stdout_path=None, stderr_path=None)
    _patch_common(monkeypatch, pinfo, plist_info=plist_info)
    cfg = Config.from_env({"AGENTS_DIR": str(tmp_path)})

    detail = build_detail(cfg, "com.a")

    assert detail.stdout_path == "/print/out.log"
    assert detail.stderr_path == "/print/err.log"


def test_stdout_stderr_falls_back_to_print_when_no_plist_resolves(tmp_path, monkeypatch):
    pinfo = _pinfo(plist_path=None, stdout_path="/print/out.log", stderr_path="/print/err.log")
    _patch_common(monkeypatch, pinfo, plist_info=None)
    cfg = Config.from_env({"AGENTS_DIR": str(tmp_path)})

    detail = build_detail(cfg, "com.a")

    assert detail.stdout_path == "/print/out.log"
    assert detail.stderr_path == "/print/err.log"
    assert detail.plist_path is None


def test_program_arguments_print_wins_when_nonempty(tmp_path, monkeypatch):
    plist_path = tmp_path / "com.a.plist"
    plist_path.write_bytes(b"")
    pinfo = _pinfo(plist_path=str(plist_path), program_arguments=["/print/bin"])
    plist_info = _plist_info(program_arguments=["/plist/bin"])
    _patch_common(monkeypatch, pinfo, plist_info=plist_info)
    cfg = Config.from_env({"AGENTS_DIR": str(tmp_path)})

    detail = build_detail(cfg, "com.a")

    assert detail.program_arguments == ["/print/bin"]


def test_program_arguments_falls_back_to_plist_when_print_empty(tmp_path, monkeypatch):
    plist_path = tmp_path / "com.a.plist"
    plist_path.write_bytes(b"")
    pinfo = _pinfo(plist_path=str(plist_path), program_arguments=[])
    plist_info = _plist_info(program_arguments=["/plist/bin"])
    _patch_common(monkeypatch, pinfo, plist_info=plist_info)
    cfg = Config.from_env({"AGENTS_DIR": str(tmp_path)})

    detail = build_detail(cfg, "com.a")

    assert detail.program_arguments == ["/plist/bin"]


def test_plist_path_prefers_print_reported_path(tmp_path, monkeypatch):
    # print reports a path that differs from the agents-dir fallback location
    # (_find_plist would find tmp_path/com.a.plist); print's value must win.
    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()
    printed_path = other_dir / "com.a.plist"
    printed_path.write_bytes(b"")
    fallback_path = tmp_path / "com.a.plist"
    fallback_path.write_bytes(b"")
    pinfo = _pinfo(plist_path=str(printed_path))
    plist_info = _plist_info()
    _patch_common(monkeypatch, pinfo, plist_info=plist_info)
    cfg = Config.from_env({"AGENTS_DIR": str(tmp_path)})

    detail = build_detail(cfg, "com.a")

    assert detail.plist_path == printed_path


def test_plist_path_falls_back_to_find_plist_when_print_has_none(tmp_path, monkeypatch):
    plist_path = tmp_path / "com.a.plist"
    plist_path.write_bytes(b"")
    pinfo = _pinfo(plist_path=None)
    plist_info = _plist_info()
    _patch_common(monkeypatch, pinfo, plist_info=plist_info)
    cfg = Config.from_env({"AGENTS_DIR": str(tmp_path)})

    detail = build_detail(cfg, "com.a")

    assert detail.plist_path == plist_path


def test_plist_path_none_when_neither_source_has_it(tmp_path, monkeypatch):
    pinfo = _pinfo(plist_path=None)
    _patch_common(monkeypatch, pinfo, plist_info=None)
    cfg = Config.from_env({"AGENTS_DIR": str(tmp_path)})

    detail = build_detail(cfg, "com.a")

    assert detail.plist_path is None


def test_loaded_true_iff_label_in_launchctl_list(tmp_path, monkeypatch):
    pinfo = _pinfo()
    _patch_common(monkeypatch, pinfo, plist_info=None, loaded=True)
    cfg = Config.from_env({"AGENTS_DIR": str(tmp_path)})

    detail = build_detail(cfg, "com.a")

    assert detail.loaded is True


def test_loaded_false_when_label_absent_from_launchctl_list(tmp_path, monkeypatch):
    pinfo = _pinfo()
    _patch_common(monkeypatch, pinfo, plist_info=None, loaded=False)
    cfg = Config.from_env({"AGENTS_DIR": str(tmp_path)})

    detail = build_detail(cfg, "com.a")

    assert detail.loaded is False


def test_disabled_from_print_disabled_independent_of_others(tmp_path, monkeypatch):
    pinfo = _pinfo()
    _patch_common(monkeypatch, pinfo, plist_info=None, loaded=True, disabled=True)
    cfg = Config.from_env({"AGENTS_DIR": str(tmp_path)})

    detail = build_detail(cfg, "com.a")

    assert detail.disabled is True

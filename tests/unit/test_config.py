from pathlib import Path

from launchd_monitor import Config


def test_from_env_defaults():
    cfg = Config.from_env({})
    assert cfg.scope == "agents"
    assert cfg.label_glob == ""
    assert cfg.agents_dir == Path("~/Library/LaunchAgents").expanduser()
    assert cfg.terminal == "ghostty"
    assert cfg.log_tool == "tail"
    assert cfg.log_stream == "out"
    assert cfg.log_lines == 200


def test_from_env_overrides_and_expands():
    cfg = Config.from_env(
        {
            "SCOPE": "gui",
            "LABEL_GLOB": "com.brandon.*",
            "AGENTS_DIR": "~/Custom/Agents",
            "TERMINAL": "iterm",
            "LOG_TOOL": "lnav",
            "LOG_STREAM": "both",
            "LOG_LINES": "50",
        }
    )
    assert cfg.scope == "gui"
    assert cfg.label_glob == "com.brandon.*"
    assert cfg.agents_dir == Path("~/Custom/Agents").expanduser()
    assert cfg.terminal == "iterm"
    assert cfg.log_tool == "lnav"
    assert cfg.log_stream == "both"
    assert cfg.log_lines == 50


def test_from_env_bad_log_lines_falls_back():
    assert Config.from_env({"LOG_LINES": "notanumber"}).log_lines == 200
    assert Config.from_env({"LOG_LINES": ""}).log_lines == 200

from pathlib import Path

import pytest

from launchd_monitor import read_plist

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_read_plist():
    info = read_plist(FIXTURES / "sample.plist")
    assert info.label == "com.brandon.morning-brief"
    assert info.stdout_path == "/Users/brandon/Library/Logs/morning-brief.out.log"
    assert info.stderr_path == "/Users/brandon/Library/Logs/morning-brief.err.log"
    assert info.program_arguments == ["/usr/bin/python3", "/Users/brandon/bin/brief.py"]
    assert info.working_dir == "/Users/brandon"


def test_read_plist_missing_file_raises():
    with pytest.raises(OSError):
        read_plist(FIXTURES / "does-not-exist.plist")

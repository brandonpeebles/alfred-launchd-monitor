from pathlib import Path

from launchd_monitor import parse_launchctl_print

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_print_running():
    info = parse_launchctl_print((FIXTURES / "print_running.txt").read_text(encoding="utf-8"))
    assert info.plist_path == "/Users/brandon/Library/LaunchAgents/com.brandon.running-job.plist"
    assert info.pid == 4821
    assert info.last_exit_code == 0
    assert info.state == "running"
    assert info.program_arguments == ["/usr/bin/python3", "/Users/brandon/bin/job.py"]
    assert info.stdout_path == "/Users/brandon/Library/Logs/job.out.log"
    assert info.stderr_path == "/Users/brandon/Library/Logs/job.err.log"
    assert info.working_dir == "/Users/brandon"


def test_parse_print_exited():
    info = parse_launchctl_print((FIXTURES / "print_exited.txt").read_text(encoding="utf-8"))
    assert info.pid is None
    assert info.last_exit_code == 78
    assert info.state == "not running"
    assert info.program_arguments == []
    assert info.stdout_path is None


def test_parse_print_empty():
    info = parse_launchctl_print("")
    assert info.pid is None
    assert info.plist_path is None
    assert info.program_arguments == []

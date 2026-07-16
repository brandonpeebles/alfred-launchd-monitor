from pathlib import Path

from launchd_monitor import parse_launchctl_list, parse_print_disabled

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_launchctl_list():
    entries = parse_launchctl_list((FIXTURES / "launchctl_list.txt").read_text(encoding="utf-8"))
    assert set(entries) == {
        "com.brandon.morning-brief",
        "com.brandon.running-job",
        "com.brandon.failing-job",
        "com.apple.some.service",
    }
    assert entries["com.brandon.running-job"].pid == 4821
    assert entries["com.brandon.morning-brief"].pid is None
    assert entries["com.brandon.failing-job"].last_status == 78


def test_parse_launchctl_list_ignores_header_and_blanks():
    assert parse_launchctl_list("PID\tStatus\tLabel\n\n") == {}


def test_parse_print_disabled():
    disabled = parse_print_disabled(
        (FIXTURES / "print_disabled.txt").read_text(encoding="utf-8")
    )
    assert disabled == {
        "com.brandon.morning-brief": False,
        "com.brandon.disabled-job": True,
    }

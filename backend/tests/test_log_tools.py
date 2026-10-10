"""
Tests for app.tools.log_tools.

Writes a real small log file to a tmp_path directory and parses it for
real — no mocking.
"""

import pytest

from app.tools.log_tools import (
    filter_by_level,
    get_logs_by_request_id,
    read_log_entries,
    search_logs,
)

_SAMPLE_LOG = """\
2026-09-10 08:12:01 | INFO | request_id=a1b2c3d4 | POST /api/auth/login | request received
2026-09-10 08:12:03 | ERROR | request_id=a1b2c3d4 | POST /api/auth/login | KeyError: 'JWT_SECRET_KEY'
2026-09-10 08:12:03 | INFO | request_id=a1b2c3d4 | POST /api/auth/login | responded 500
2026-09-10 08:15:00 | INFO | request_id=e5f6a7b8 | GET /health | responded 200
this line does not match the expected format at all
"""


@pytest.fixture
def log_file(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "app.log").write_text(_SAMPLE_LOG)
    return tmp_path


def test_read_log_entries_parses_all_well_formed_lines(log_file):
    entries = read_log_entries(log_file, "logs/app.log")

    assert len(entries) == 5  # including the one malformed line
    assert entries[0].level == "INFO"
    assert entries[1].level == "ERROR"
    assert entries[1].request_id == "a1b2c3d4"
    assert "KeyError" in entries[1].message


def test_malformed_line_is_kept_with_unknown_level(log_file):
    entries = read_log_entries(log_file, "logs/app.log")

    unknown = [e for e in entries if e.level == "UNKNOWN"]
    assert len(unknown) == 1
    assert "does not match" in unknown[0].message


def test_read_log_entries_raises_for_missing_file(log_file):
    with pytest.raises(FileNotFoundError):
        read_log_entries(log_file, "logs/does_not_exist.log")


def test_search_logs_finds_keyword_in_message(log_file):
    entries = read_log_entries(log_file, "logs/app.log")
    matches = search_logs(entries, "JWT_SECRET_KEY")

    assert len(matches) == 1
    assert matches[0].level == "ERROR"


def test_filter_by_level_returns_only_matching_level(log_file):
    entries = read_log_entries(log_file, "logs/app.log")
    errors = filter_by_level(entries, "error")

    assert len(errors) == 1
    assert errors[0].level == "ERROR"


def test_get_logs_by_request_id_groups_related_entries(log_file):
    entries = read_log_entries(log_file, "logs/app.log")
    related = get_logs_by_request_id(entries, "a1b2c3d4")

    assert len(related) == 3
    assert all(e.request_id == "a1b2c3d4" for e in related)

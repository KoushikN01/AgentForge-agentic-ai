"""
Tests for app.tools.repo_tools.

Uses pytest's tmp_path fixture to create a real throwaway directory on
disk for each test — these are genuine filesystem operations, not mocks.
"""

import pytest

from app.tools.repo_tools import list_files, read_file, search_repository
from app.tools.security import PathSecurityError


@pytest.fixture
def sample_repo(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("def handler():\n    return call_db()\n")
    (tmp_path / "app" / "db.py").write_text("def call_db():\n    raise ConnectionError('timeout')\n")
    (tmp_path / "README.md").write_text("# Sample\nJust a readme.\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("should be ignored")
    return tmp_path


def test_list_files_finds_python_files_and_ignores_git_dir(sample_repo):
    result = list_files(sample_repo, pattern="*.py")
    paths = {f.path for f in result}

    assert paths == {"app/main.py", "app/db.py"}


def test_list_files_default_pattern_finds_everything_except_ignored_dirs(sample_repo):
    result = list_files(sample_repo)
    paths = {f.path for f in result}

    assert "app/main.py" in paths
    assert "README.md" in paths
    assert not any(".git" in p for p in paths)


def test_read_file_returns_contents(sample_repo):
    content = read_file(sample_repo, "app/db.py")

    assert "ConnectionError" in content


def test_read_file_raises_for_missing_file(sample_repo):
    with pytest.raises(FileNotFoundError):
        read_file(sample_repo, "app/does_not_exist.py")


def test_read_file_rejects_path_traversal(sample_repo):
    with pytest.raises(PathSecurityError):
        read_file(sample_repo, "../../etc/passwd")


def test_search_repository_finds_matching_line_with_location(sample_repo):
    matches = search_repository(sample_repo, "ConnectionError")

    assert len(matches) == 1
    assert matches[0].path == "app/db.py"
    assert matches[0].line_number == 2
    assert "ConnectionError" in matches[0].line


def test_search_repository_is_case_insensitive(sample_repo):
    matches = search_repository(sample_repo, "connectionerror")

    assert len(matches) == 1


def test_search_repository_returns_empty_list_when_nothing_matches(sample_repo):
    matches = search_repository(sample_repo, "nonexistent_symbol_xyz")

    assert matches == []

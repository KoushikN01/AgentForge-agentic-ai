"""
Tests for app.tools.git_tools.

Initializes a real throwaway git repository in tmp_path and runs real git
subprocess commands against it — not mocked.
"""

import subprocess

import pytest

from app.tools.git_tools import NotAGitRepositoryError, get_diff


def _git(repo_path, *args):
    subprocess.run(["git", "-C", str(repo_path), *args], check=True, capture_output=True)


@pytest.fixture
def git_repo(tmp_path):
    (tmp_path / "app.py").write_text("value = 1\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "initial commit")
    return tmp_path


def test_get_diff_reports_no_changes_on_clean_repo(git_repo):
    result = get_diff(git_repo)

    assert result.has_changes is False
    assert result.diff == ""


def test_get_diff_reports_changes_after_editing_a_file(git_repo):
    (git_repo / "app.py").write_text("value = 2\n")

    result = get_diff(git_repo)

    assert result.has_changes is True
    assert "-value = 1" in result.diff
    assert "+value = 2" in result.diff


def test_get_diff_raises_for_non_git_directory(tmp_path):
    not_a_repo = tmp_path / "plain_folder"
    not_a_repo.mkdir()

    with pytest.raises(NotAGitRepositoryError):
        get_diff(not_a_repo)

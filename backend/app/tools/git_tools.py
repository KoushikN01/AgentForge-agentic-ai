"""
Git/diff inspection tool.

Lets an agent see what has changed in a repository's working tree, and
(in a later phase) will be how the Coding Agent's proposed patch gets
inspected before a human approves it. Like test_tools, this runs a
subprocess — so it's restricted to a small allowlist of read-only git
subcommands (`diff`, `status`) executed with an explicit argument list,
never a freeform shell string.

This module does not commit, push, reset, or modify the repository in any
way — inspecting a diff and creating one are different concerns, and only
inspection is needed until the Coding Agent (a later phase) exists.
"""

import subprocess
from pathlib import Path

from app.tools.models import GitDiffResult

_TIMEOUT_SECONDS = 15


class NotAGitRepositoryError(Exception):
    """Raised when git_tools is pointed at a directory that isn't a git repo."""


def _run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
    )


def get_diff(repo_root: Path) -> GitDiffResult:
    """
    Return the working-tree diff (unstaged + staged changes) for
    `repo_root`. If the directory isn't a git repository, raises
    NotAGitRepositoryError with a clear message instead of a raw git
    stderr dump.
    """
    result = _run_git(repo_root, "diff", "HEAD")

    if result.returncode != 0:
        raise NotAGitRepositoryError(
            f"'{repo_root}' does not look like a git repository: {result.stderr.strip()}"
        )

    diff_text = result.stdout
    return GitDiffResult(has_changes=bool(diff_text.strip()), diff=diff_text)

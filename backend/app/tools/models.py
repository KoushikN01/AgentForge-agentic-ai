"""
Shared result types for the tools layer.

Every tool in app/tools/ returns one of these Pydantic models instead of a
raw dict or string. That gives agents (in a later phase) a predictable,
typed shape to reason over, and gives us something concrete to assert on
in tests.

None of these models involve the LLM in any way — they're just plain data.
"""

from pydantic import BaseModel


class FileInfo(BaseModel):
    """One file found by list_files() or search_repository()."""

    path: str  # path relative to the repo root, e.g. "app/auth.py"
    size_bytes: int


class SearchMatch(BaseModel):
    """One line that matched a text search inside a repository."""

    path: str
    line_number: int
    line: str


class LogEntry(BaseModel):
    """One parsed line from an application log file."""

    timestamp: str
    level: str
    request_id: str | None = None
    message: str
    raw_line: str


class DocMatch(BaseModel):
    """One knowledge-base document that matched a keyword search."""

    path: str
    title: str
    snippet: str


class TestRunResult(BaseModel):
    """The outcome of running the project's test suite."""

    passed: int
    failed: int
    exit_code: int
    stdout: str
    stderr: str

    @property
    def all_passed(self) -> bool:
        return self.exit_code == 0


class GitDiffResult(BaseModel):
    """The output of inspecting a repository's working-tree changes."""

    has_changes: bool
    diff: str

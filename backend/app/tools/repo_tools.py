"""
Repository/file inspection tool.

Lets an agent (in a later phase) look at a project's source code without
any LLM involvement — listing files, reading one file, and doing a plain
text search across files. All three are ordinary deterministic Python: no
reason to spend a Gemini call on "read this file".

Every function takes a `root` directory and only ever looks inside it
(enforced by app.tools.security.resolve_within_root) — this is the
"Repository tools" allowlisted capability from the project's safety
requirements. There is deliberately no function here that writes, deletes,
or executes anything.
"""

import fnmatch
from pathlib import Path

from app.tools.models import FileInfo, SearchMatch
from app.tools.security import resolve_within_root

# Skip directories that aren't meaningful source content — no point
# listing/searching through virtual envs, caches, or git internals.
_IGNORED_DIRS = {".git", "__pycache__", ".pytest_cache", "venv", ".venv", "node_modules"}


def list_files(root: Path, pattern: str = "*") -> list[FileInfo]:
    """
    List files under `root` (recursively) whose name matches `pattern`
    (a glob pattern, e.g. "*.py"). Returns them sorted by path so results
    are stable and easy to test/read.
    """
    root = root.resolve()
    results: list[FileInfo] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(ignored in path.parts for ignored in _IGNORED_DIRS):
            continue
        if not fnmatch.fnmatch(path.name, pattern):
            continue

        results.append(
            FileInfo(
                path=path.relative_to(root).as_posix(),
                size_bytes=path.stat().st_size,
            )
        )
    return results


def read_file(root: Path, relative_path: str) -> str:
    """
    Read one text file's contents. `relative_path` must resolve to
    somewhere inside `root` — see app.tools.security for why.
    """
    file_path = resolve_within_root(root, relative_path)
    if not file_path.is_file():
        raise FileNotFoundError(f"No such file: {relative_path}")
    return file_path.read_text(encoding="utf-8")


def search_repository(root: Path, query: str, pattern: str = "*.py") -> list[SearchMatch]:
    """
    Search for a plain-text substring across files matching `pattern`
    under `root`. Case-insensitive. This is a simple grep, not semantic
    search — that's what the RAG tool (doc_tools) and Phase 3's vector
    search are for.
    """
    query_lower = query.lower()
    matches: list[SearchMatch] = []

    for file_info in list_files(root, pattern):
        content = read_file(root, file_info.path)
        for line_number, line in enumerate(content.splitlines(), start=1):
            if query_lower in line.lower():
                matches.append(
                    SearchMatch(path=file_info.path, line_number=line_number, line=line.strip())
                )
    return matches

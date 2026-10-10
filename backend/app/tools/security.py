"""
Path safety helper shared by every tool that reads from a directory on
disk (repo_tools, log_tools, doc_tools).

This is the guardrail the project spec asks for: a tool is given a root
directory (e.g. the sample_project folder) and a relative path, and this
function makes sure the resolved path can never escape that root — so a
request like read_file(root, "../../../etc/passwd") is rejected instead of
quietly reading files outside the intended workspace.
"""

from pathlib import Path


class PathSecurityError(Exception):
    """Raised when a requested path would resolve outside its allowed root."""


def resolve_within_root(root: Path, relative_path: str) -> Path:
    """
    Resolve `relative_path` against `root` and confirm the result is still
    inside `root`. Returns the resolved absolute Path if safe, otherwise
    raises PathSecurityError.
    """
    root = root.resolve()
    candidate = (root / relative_path).resolve()

    if root not in candidate.parents and candidate != root:
        raise PathSecurityError(
            f"Path '{relative_path}' resolves outside the allowed root '{root}'."
        )
    return candidate

"""
Sandbox workspace management for the Coding Agent's proposed fixes.

This is the project's core safety mechanism for code changes: a patch is
NEVER applied to the real sample_project/ directory by an agent. Every
patch is applied to a fresh, throwaway COPY in a temp directory. Only a
human approving the change results in anything reaching the real project.

    sample_project/  (real, untouched)
        | copy
    /tmp/agentforge_workspace_xxxx/  (throwaway sandbox)
        | apply_patch()
    modified copy
        | test_tools.run_tests()
    pass/fail - the real project was never touched
"""

import difflib
import shutil
import tempfile
from pathlib import Path

from app.models.agent_outputs import PatchProposal
from app.tools.security import resolve_within_root

# Same ignore list as repo_tools - no point copying caches/vcs internals.
_IGNORED = {".git", "__pycache__", ".pytest_cache", "venv", ".venv"}


class PatchApplyError(Exception):
    """Raised when a PatchProposal's original_snippet can't be safely applied."""


def create_incident_workspace(sample_project_root: Path) -> Path:
    """
    Copy sample_project_root into a fresh temp directory and return its
    path. Every call makes a brand new sandbox; old ones are simply
    abandoned to the OS's /tmp cleanup (a learning project, not a
    long-running service, so no cleanup machinery).
    """
    workspace = Path(tempfile.mkdtemp(prefix="agentforge_workspace_"))
    shutil.copytree(
        sample_project_root,
        workspace,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(*_IGNORED),
    )
    return workspace


def apply_patch(workspace_root: Path, patch: PatchProposal) -> None:
    """
    Apply a PatchProposal to a sandbox workspace: find `original_snippet`
    in `target_file` and replace it with `replacement_snippet`.

    Raises PatchApplyError (never a silent no-op) if the snippet is
    missing or appears more than once - a stale or ambiguous patch should
    fail loudly rather than apply to the wrong place.
    """
    file_path = resolve_within_root(workspace_root, patch.target_file)
    if not file_path.is_file():
        raise PatchApplyError(f"Patch target file does not exist: {patch.target_file}")

    content = file_path.read_text(encoding="utf-8")
    occurrences = content.count(patch.original_snippet)

    if occurrences == 0:
        raise PatchApplyError(
            f"original_snippet was not found in {patch.target_file} - "
            "the patch doesn't match the current file content."
        )
    if occurrences > 1:
        raise PatchApplyError(
            f"original_snippet appears {occurrences} times in {patch.target_file} - "
            "too ambiguous to safely apply."
        )

    file_path.write_text(content.replace(patch.original_snippet, patch.replacement_snippet), encoding="utf-8")


def compute_diff(sample_project_root: Path, workspace_root: Path, relative_path: str) -> str:
    """
    Unified diff between the original file (real project) and the modified
    one (sandbox), for the Review Agent and a human approver to read.
    """
    original_path = resolve_within_root(sample_project_root, relative_path)
    modified_path = resolve_within_root(workspace_root, relative_path)

    diff = difflib.unified_diff(
        original_path.read_text(encoding="utf-8").splitlines(keepends=True),
        modified_path.read_text(encoding="utf-8").splitlines(keepends=True),
        fromfile=f"a/{relative_path}",
        tofile=f"b/{relative_path}",
    )
    return "".join(diff)


def cleanup_workspace(workspace_root: Path) -> None:
    """
    Delete a sandbox workspace once it's no longer needed - after a human
    has approved or rejected the fix (app.agents.human_approval), or after
    an investigation reaches FAILED without ever reaching approval.

    Deliberately NOT called by anything that runs before a human decision:
    the workspace is how the Review Agent and a human approver see the
    actual diff, and it's where apply_patch_to_real_project copies the
    approved fix FROM - deleting it earlier would destroy information
    that's still needed. Safe to call on a path that's already gone
    (ignore_errors) - cleanup is best-effort, not load-bearing.
    """
    shutil.rmtree(workspace_root, ignore_errors=True)


def apply_patch_to_real_project(sample_project_root: Path, workspace_root: Path, relative_path: str) -> None:
    """
    Copy the fixed file from the sandbox back into the REAL project.

    The one function allowed to modify the real project - and it is only
    called from app/agents/human_approval.apply_human_decision(), and only
    when a human has approved.
    """
    workspace_file = resolve_within_root(workspace_root, relative_path)
    real_file = resolve_within_root(sample_project_root, relative_path)

    if not workspace_file.is_file():
        raise PatchApplyError(f"Nothing to apply - {relative_path} does not exist in the workspace.")

    real_file.write_text(workspace_file.read_text(encoding="utf-8"), encoding="utf-8")

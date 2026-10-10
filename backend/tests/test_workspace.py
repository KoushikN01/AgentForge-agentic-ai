"""Tests for app.agents.workspace - real filesystem operations, no mocking."""

import pytest

from app.agents.workspace import (
    PatchApplyError,
    apply_patch,
    apply_patch_to_real_project,
    compute_diff,
    create_incident_workspace,
)
from app.models.agent_outputs import PatchProposal


@pytest.fixture
def fake_project(tmp_path):
    project = tmp_path / "fake_project"
    (project / "app").mkdir(parents=True)
    (project / "app" / "auth.py").write_text("secret = os.environ['JWT_SECRET_KEY']\n")
    (project / ".git").mkdir()
    (project / ".git" / "config").write_text("should not be copied")
    (project / "__pycache__").mkdir()
    (project / "__pycache__" / "junk.pyc").write_text("should not be copied")
    return project


def make_patch(**overrides) -> PatchProposal:
    defaults = dict(
        target_file="app/auth.py",
        explanation="Fix the env var name",
        original_snippet="os.environ['JWT_SECRET_KEY']",
        replacement_snippet="os.environ['JWT_SECRET']",
        relevant_test_path="tests/test_auth.py",
    )
    defaults.update(overrides)
    return PatchProposal(**defaults)


def test_workspace_copies_real_files(fake_project):
    workspace = create_incident_workspace(fake_project)
    assert (workspace / "app" / "auth.py").read_text() == (fake_project / "app" / "auth.py").read_text()


def test_workspace_excludes_git_and_pycache(fake_project):
    workspace = create_incident_workspace(fake_project)
    assert not (workspace / ".git").exists()
    assert not (workspace / "__pycache__").exists()


def test_workspace_is_independent_of_the_original(fake_project):
    workspace = create_incident_workspace(fake_project)
    (workspace / "app" / "auth.py").write_text("modified")
    assert (fake_project / "app" / "auth.py").read_text() != "modified"


def test_apply_patch_replaces_snippet_and_leaves_original_alone(fake_project):
    workspace = create_incident_workspace(fake_project)
    apply_patch(workspace, make_patch())
    assert (workspace / "app" / "auth.py").read_text() == "secret = os.environ['JWT_SECRET']\n"
    assert "JWT_SECRET_KEY" in (fake_project / "app" / "auth.py").read_text()


def test_apply_patch_raises_when_snippet_not_found(fake_project):
    workspace = create_incident_workspace(fake_project)
    with pytest.raises(PatchApplyError, match="not found"):
        apply_patch(workspace, make_patch(original_snippet="this text does not exist"))


def test_apply_patch_raises_when_snippet_is_ambiguous(fake_project):
    (fake_project / "app" / "auth.py").write_text("x = 1\nx = 1\n")
    workspace = create_incident_workspace(fake_project)
    with pytest.raises(PatchApplyError, match="ambiguous"):
        apply_patch(workspace, make_patch(original_snippet="x = 1"))


def test_apply_patch_raises_when_target_file_missing(fake_project):
    workspace = create_incident_workspace(fake_project)
    with pytest.raises(PatchApplyError, match="does not exist"):
        apply_patch(workspace, make_patch(target_file="app/nope.py"))


def test_apply_patch_rejects_path_traversal(fake_project):
    from app.tools.security import PathSecurityError

    workspace = create_incident_workspace(fake_project)
    with pytest.raises(PathSecurityError):
        apply_patch(workspace, make_patch(target_file="../../etc/passwd"))


def test_compute_diff_shows_the_change(fake_project):
    workspace = create_incident_workspace(fake_project)
    apply_patch(workspace, make_patch())
    diff = compute_diff(fake_project, workspace, "app/auth.py")
    assert "-secret = os.environ['JWT_SECRET_KEY']" in diff
    assert "+secret = os.environ['JWT_SECRET']" in diff


def test_compute_diff_is_empty_when_nothing_changed(fake_project):
    workspace = create_incident_workspace(fake_project)
    assert compute_diff(fake_project, workspace, "app/auth.py") == ""


def test_apply_patch_to_real_project_copies_workspace_file_back(fake_project):
    workspace = create_incident_workspace(fake_project)
    apply_patch(workspace, make_patch())
    apply_patch_to_real_project(fake_project, workspace, "app/auth.py")
    assert (fake_project / "app" / "auth.py").read_text() == "secret = os.environ['JWT_SECRET']\n"

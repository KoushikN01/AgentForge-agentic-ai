"""
Tests for app.tools.doc_tools.

Writes real markdown files to tmp_path and searches them for real.
"""

import pytest

from app.tools.doc_tools import get_document, list_documents, search_docs


@pytest.fixture
def sample_kb(tmp_path):
    (tmp_path / "runbook.md").write_text(
        "# Incident Runbook\n\nIf login returns 500, check the JWT_SECRET "
        "environment variable is set correctly before restarting the service.\n"
    )
    (tmp_path / "deployment_notes.md").write_text(
        "# Deployment Notes\n\nAll required environment variables must be set "
        "before the app starts, or startup will fail.\n"
    )
    (tmp_path / "unrelated.md").write_text("# Unrelated\n\nThis document is about something else.\n")
    return tmp_path


def test_list_documents_finds_all_markdown_files(sample_kb):
    docs = list_documents(sample_kb)

    assert set(docs) == {"runbook.md", "deployment_notes.md", "unrelated.md"}


def test_get_document_returns_full_content(sample_kb):
    content = get_document(sample_kb, "runbook.md")

    assert "JWT_SECRET" in content


def test_search_docs_finds_matching_documents_only(sample_kb):
    matches = search_docs(sample_kb, "JWT_SECRET")

    assert len(matches) == 1
    assert matches[0].path == "runbook.md"
    assert matches[0].title == "Incident Runbook"
    assert "JWT_SECRET" in matches[0].snippet


def test_search_docs_is_case_insensitive(sample_kb):
    matches = search_docs(sample_kb, "environment variable")

    paths = {m.path for m in matches}
    assert "runbook.md" in paths
    assert "deployment_notes.md" in paths
    assert "unrelated.md" not in paths


def test_search_docs_returns_empty_list_when_nothing_matches(sample_kb):
    matches = search_docs(sample_kb, "nonexistent_topic_xyz")

    assert matches == []

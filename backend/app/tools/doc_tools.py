"""
Documentation / knowledge-base access tool.

Phase 2 implements this as plain keyword search over the markdown files in
knowledge_base/ — no embeddings, no vector store, no LLM call. That's
intentional: Phase 3 (RAG) will replace the *retrieval* behind
search_docs() with a real embeddings + vector store pipeline, but the
knowledge_base/ folder structure and the DocMatch shape returned here are
designed to stay the same, so nothing above this module (agents, in a
later phase) needs to change when that happens.

Traditional RAG vs. what this module does today:
    Question -> keyword match -> return matching docs

Agentic RAG (Phase 3+) will look more like:
    Incident -> decide what to search for -> retrieve -> is it enough? -> retrieve again if not

This module is the "retrieve" step both versions will eventually call.
"""

from pathlib import Path

from app.tools import repo_tools
from app.tools.models import DocMatch

_SNIPPET_RADIUS = 80  # characters of context to show on each side of a match


def _extract_title(content: str, fallback: str) -> str:
    """Use the file's first markdown heading as its title, if it has one."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return fallback


def list_documents(root: Path) -> list[str]:
    """List every markdown document path in the knowledge base."""
    return [f.path for f in repo_tools.list_files(root, pattern="*.md")]


def get_document(root: Path, relative_path: str) -> str:
    """Read one document's full raw content."""
    return repo_tools.read_file(root, relative_path)


def search_docs(root: Path, query: str) -> list[DocMatch]:
    """
    Case-insensitive keyword search across every markdown document in the
    knowledge base. Returns one DocMatch per matching document (not per
    line — for documentation, "does this doc cover the topic" matters
    more than exactly which line), with a short snippet of surrounding
    text so the caller can judge relevance without reading the whole doc.
    """
    query_lower = query.lower()
    matches: list[DocMatch] = []

    for path in list_documents(root):
        content = get_document(root, path)
        content_lower = content.lower()
        match_index = content_lower.find(query_lower)
        if match_index == -1:
            continue

        start = max(0, match_index - _SNIPPET_RADIUS)
        end = min(len(content), match_index + len(query) + _SNIPPET_RADIUS)
        snippet = content[start:end].strip().replace("\n", " ")

        matches.append(
            DocMatch(
                path=path,
                title=_extract_title(content, fallback=path),
                snippet=snippet,
            )
        )
    return matches

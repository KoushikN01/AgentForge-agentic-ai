"""
Tests for app.rag.ingest.

GeminiClient.embed_texts is mocked (no real API key/network), but
everything else — reading knowledge_base/*.md via doc_tools, chunking,
and storing in a real Chroma collection — genuinely runs.
"""

from unittest.mock import MagicMock

import pytest

from app.rag.ingest import build_chunks, ingest_knowledge_base


@pytest.fixture
def sample_kb(tmp_path):
    (tmp_path / "runbook.md").write_text(
        "# Runbook\n\nIf login fails, check the JWT_SECRET environment variable.\n"
    )
    (tmp_path / "orders.md").write_text(
        "# Orders\n\nOrder totals include sales tax at the configured TAX_RATE.\n"
    )
    return tmp_path


def make_stub_gemini_client(vector_size: int = 4):
    """A fake GeminiClient that returns a deterministic vector per text
    (based on the text's length) instead of calling the real Gemini API."""
    client = MagicMock()

    def fake_embed(texts, task_type="RETRIEVAL_DOCUMENT"):
        return [[float(len(t) % 17)] * vector_size for t in texts]

    client.embed_texts.side_effect = fake_embed
    return client


def test_build_chunks_reads_and_chunks_every_document(sample_kb):
    chunks = build_chunks(sample_kb)

    source_paths = {c.source_path for c in chunks}
    assert source_paths == {"runbook.md", "orders.md"}
    assert any("JWT_SECRET" in c.text for c in chunks)
    assert any("TAX_RATE" in c.text for c in chunks)


def test_build_chunks_returns_empty_list_for_empty_knowledge_base(tmp_path):
    assert build_chunks(tmp_path) == []


def test_ingest_knowledge_base_populates_a_queryable_collection(sample_kb):
    stub_client = make_stub_gemini_client()

    collection = ingest_knowledge_base(sample_kb, stub_client)

    expected_chunk_count = len(build_chunks(sample_kb))
    assert collection.count() == expected_chunk_count
    stub_client.embed_texts.assert_called_once()
    _, kwargs = stub_client.embed_texts.call_args
    assert kwargs["task_type"] == "RETRIEVAL_DOCUMENT"

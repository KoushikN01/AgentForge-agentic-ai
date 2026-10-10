"""
Tests for app.rag.vector_store.

These use a REAL in-memory Chroma collection — not mocked — with small
hand-made embedding vectors instead of real Gemini embeddings, so the
tests need no API key and no network, while still proving Chroma storage
and similarity search genuinely work.
"""

import pytest

from app.rag.models import Chunk
from app.rag.vector_store import add_chunks, build_collection, query_collection


def make_chunk(chunk_id: str, source_path: str, text: str) -> Chunk:
    return Chunk(id=chunk_id, source_path=source_path, chunk_index=0, text=text)


def test_build_collection_starts_empty():
    collection = build_collection("test_empty")

    assert collection.count() == 0


def test_add_chunks_rejects_mismatched_lengths():
    collection = build_collection("test_mismatch")
    chunks = [make_chunk("a::0", "a.md", "hello")]

    with pytest.raises(ValueError, match="chunks"):
        add_chunks(collection, chunks, embeddings=[[0.1], [0.2]])


def test_query_collection_returns_closest_match_first():
    collection = build_collection("test_query")
    chunks = [
        make_chunk("near::0", "near.md", "the closest chunk"),
        make_chunk("far::0", "far.md", "a completely unrelated chunk"),
    ]
    # Simple 2D vectors placed so "near" is obviously closer to the query
    # than "far" — real Gemini embeddings would be 768-dimensional, but
    # the similarity math works the same regardless of dimensionality.
    embeddings = [[1.0, 0.0], [-1.0, 0.0]]
    add_chunks(collection, chunks, embeddings)

    results = query_collection(collection, query_embedding=[0.9, 0.1], n_results=2)

    assert len(results) == 2
    assert results[0].chunk.id == "near::0"
    assert results[1].chunk.id == "far::0"
    assert results[0].distance < results[1].distance


def test_query_collection_respects_n_results():
    collection = build_collection("test_n_results")
    chunks = [make_chunk(f"c{i}::0", "doc.md", f"chunk {i}") for i in range(5)]
    embeddings = [[float(i), 0.0] for i in range(5)]
    add_chunks(collection, chunks, embeddings)

    results = query_collection(collection, query_embedding=[0.0, 0.0], n_results=2)

    assert len(results) == 2


def test_add_chunks_with_empty_list_is_a_no_op():
    collection = build_collection("test_empty_add")

    add_chunks(collection, [], [])

    assert collection.count() == 0


def test_build_collection_can_be_called_twice_with_same_name(tmp_path):
    # Recreating a collection with the same name shouldn't error — this
    # matters because ingestion might be re-run in the same process.
    build_collection("test_rebuild")
    second = build_collection("test_rebuild")

    assert second.count() == 0

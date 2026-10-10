"""
Vector store wrapper around Chroma (chromadb).

This is the only file in the project that imports chromadb — same
one-file-per-dependency pattern as app/llm/gemini.py, so the vector store
could be swapped (e.g. for FAISS) without touching the rest of the RAG
pipeline.

IMPORTANT: we always pass our own precomputed embeddings (from
GeminiClient.embed_texts) into Chroma, and never let Chroma compute
embeddings itself. Chroma's default behavior is to download a
sentence-transformers model the first time it's used — we don't want a
silent network dependency, and we want every embedding in the system to
come from the same Gemini model.
"""

import chromadb

from app.rag.models import Chunk, RetrievedChunk


def build_collection(name: str = "knowledge_base"):
    """
    Create a fresh, in-memory Chroma collection. In-memory is the right
    choice for a learning project's knowledge base: it's small, it's
    rebuilt from knowledge_base/*.md on every ingest run, and there's no
    need to manage a persistent database file for this phase.
    """
    client = chromadb.Client()
    # Guard against "collection already exists" if this is called twice
    # in the same process (e.g. re-running ingestion in a notebook/REPL).
    existing = {c.name for c in client.list_collections()}
    if name in existing:
        client.delete_collection(name)
    return client.create_collection(name)


def add_chunks(collection, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
    """Store chunks and their precomputed embeddings in the collection."""
    if len(chunks) != len(embeddings):
        raise ValueError(f"Got {len(chunks)} chunks but {len(embeddings)} embeddings.")
    if not chunks:
        return

    collection.add(
        ids=[c.id for c in chunks],
        embeddings=embeddings,
        documents=[c.text for c in chunks],
        metadatas=[{"source_path": c.source_path, "chunk_index": c.chunk_index} for c in chunks],
    )


def query_collection(collection, query_embedding: list[float], n_results: int = 3) -> list[RetrievedChunk]:
    """Find the n_results chunks most similar to query_embedding."""
    result = collection.query(query_embeddings=[query_embedding], n_results=n_results)

    retrieved: list[RetrievedChunk] = []
    ids = result["ids"][0]
    documents = result["documents"][0]
    metadatas = result["metadatas"][0]
    distances = result["distances"][0]

    for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
        chunk = Chunk(
            id=chunk_id,
            source_path=metadata["source_path"],
            chunk_index=metadata["chunk_index"],
            text=text,
        )
        retrieved.append(RetrievedChunk(chunk=chunk, distance=distance))
    return retrieved

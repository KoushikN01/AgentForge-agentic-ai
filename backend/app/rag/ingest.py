"""
Ingestion pipeline: reads knowledge_base/*.md, chunks it, embeds the
chunks with Gemini, and stores everything in a Chroma collection.

    knowledge_base/*.md
        ↓ doc_tools.list_documents / get_document
    raw document text
        ↓ chunking.chunk_text
    list[Chunk]
        ↓ GeminiClient.embed_texts (task_type=RETRIEVAL_DOCUMENT)
    list[list[float]]
        ↓ vector_store.add_chunks
    populated Chroma collection

This is meant to be run once whenever the knowledge base changes (see
scripts/ingest_knowledge.py), not on every query.
"""

from pathlib import Path

from app.llm.gemini import GeminiClient
from app.rag import vector_store
from app.rag.chunking import chunk_text
from app.rag.models import Chunk
from app.tools import doc_tools


def build_chunks(knowledge_base_root: Path) -> list[Chunk]:
    """Read every document in the knowledge base and split it into chunks."""
    chunks: list[Chunk] = []
    for path in doc_tools.list_documents(knowledge_base_root):
        content = doc_tools.get_document(knowledge_base_root, path)
        chunks.extend(chunk_text(content, source_path=path))
    return chunks


def ingest_knowledge_base(knowledge_base_root: Path, gemini_client: GeminiClient):
    """
    Run the full ingestion pipeline and return a populated, queryable
    Chroma collection.
    """
    chunks = build_chunks(knowledge_base_root)
    embeddings = gemini_client.embed_texts(
        [c.text for c in chunks], task_type="RETRIEVAL_DOCUMENT"
    )

    collection = vector_store.build_collection()
    vector_store.add_chunks(collection, chunks, embeddings)
    return collection

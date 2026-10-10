"""
Traditional RAG retrieval: embed a query, find the most similar chunks.

    query -> embed -> vector search -> top-k chunks

This is the "Question -> Retrieve -> Answer" pattern from the project
spec. app/rag/agentic_retrieval.py builds on top of this with the
"decide what to search for, evaluate if it's enough, retrieve again if
not" pattern.
"""

from app.llm.gemini import GeminiClient
from app.rag import vector_store
from app.rag.models import RetrievedChunk


def semantic_search(
    collection, gemini_client: GeminiClient, query: str, k: int = 3
) -> list[RetrievedChunk]:
    """Embed `query` and return the k most similar chunks in `collection`."""
    query_embedding = gemini_client.embed_texts([query], task_type="RETRIEVAL_QUERY")[0]
    return vector_store.query_collection(collection, query_embedding, n_results=k)

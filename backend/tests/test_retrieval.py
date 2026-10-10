from unittest.mock import MagicMock

from app.rag.models import Chunk
from app.rag.retrieval import semantic_search
from app.rag.vector_store import add_chunks, build_collection


def test_semantic_search_embeds_query_and_returns_closest_chunk():
    collection = build_collection("test_semantic_search")
    chunks = [
        Chunk(id="login::0", source_path="runbook.md", chunk_index=0, text="login troubleshooting"),
        Chunk(id="orders::0", source_path="orders.md", chunk_index=0, text="order tax calculation"),
    ]
    add_chunks(collection, chunks, embeddings=[[1.0, 0.0], [0.0, 1.0]])

    stub_client = MagicMock()
    stub_client.embed_texts.return_value = [[0.9, 0.1]]  # close to the "login" chunk

    results = semantic_search(collection, stub_client, "why does login fail?", k=1)

    assert len(results) == 1
    assert results[0].chunk.id == "login::0"

    stub_client.embed_texts.assert_called_once_with(
        ["why does login fail?"], task_type="RETRIEVAL_QUERY"
    )

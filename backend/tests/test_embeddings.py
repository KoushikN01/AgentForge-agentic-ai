"""
Tests for GeminiClient.embed_texts.

Mocks google.genai.Client, same pattern as test_gemini_client.py's
generate_text/generate_structured tests: proves the request is built
correctly and the response is parsed correctly, without a real API key
or network access.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.llm.gemini import GeminiClient, GeminiRequestError


def make_settings() -> Settings:
    return Settings(
        gemini_api_key="fake-test-key",
        gemini_model="gemini-2.5-flash",
        gemini_embedding_model="gemini-embedding-001",
        database_url="sqlite:///:memory:",
        log_level="INFO",
        rag_mode="vector",
    )


def _mock_embedding_response(vectors: list[list[float]]):
    embeddings = [MagicMock(values=v) for v in vectors]
    return MagicMock(embeddings=embeddings)


@patch("app.llm.gemini.genai.Client")
def test_embed_texts_returns_one_vector_per_input(mock_client_cls):
    mock_client = MagicMock()
    mock_client.models.embed_content.return_value = _mock_embedding_response(
        [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    )
    mock_client_cls.return_value = mock_client

    client = GeminiClient(config=make_settings())
    result = client.embed_texts(["first text", "second text"])

    assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

    _, kwargs = mock_client.models.embed_content.call_args
    assert kwargs["model"] == "gemini-embedding-001"
    assert kwargs["contents"] == ["first text", "second text"]
    assert kwargs["config"].task_type == "RETRIEVAL_DOCUMENT"
    assert kwargs["config"].output_dimensionality == 768


@patch("app.llm.gemini.genai.Client")
def test_embed_texts_uses_retrieval_query_task_type_when_requested(mock_client_cls):
    mock_client = MagicMock()
    mock_client.models.embed_content.return_value = _mock_embedding_response([[0.1, 0.2]])
    mock_client_cls.return_value = mock_client

    client = GeminiClient(config=make_settings())
    client.embed_texts(["a search query"], task_type="RETRIEVAL_QUERY")

    _, kwargs = mock_client.models.embed_content.call_args
    assert kwargs["config"].task_type == "RETRIEVAL_QUERY"


def test_embed_texts_returns_empty_list_for_empty_input():
    # No API key needed here — embed_texts([]) should short-circuit
    # before ever building a GeminiClient... but GeminiClient itself
    # still needs a key to construct. Use a fake key and don't mock,
    # since embed_content should never actually be called.
    with patch("app.llm.gemini.genai.Client"):
        client = GeminiClient(config=make_settings())
        assert client.embed_texts([]) == []


@patch("app.llm.gemini.genai.Client")
def test_embed_texts_raises_on_empty_response(mock_client_cls):
    mock_client = MagicMock()
    mock_client.models.embed_content.return_value = MagicMock(embeddings=[])
    mock_client_cls.return_value = mock_client

    client = GeminiClient(config=make_settings())

    with pytest.raises(GeminiRequestError, match="no embeddings"):
        client.embed_texts(["hello"])


@patch("app.llm.gemini.genai.Client")
def test_embed_texts_wraps_sdk_errors(mock_client_cls):
    mock_client = MagicMock()
    mock_client.models.embed_content.side_effect = RuntimeError("quota exceeded")
    mock_client_cls.return_value = mock_client

    client = GeminiClient(config=make_settings())

    with pytest.raises(GeminiRequestError, match="quota exceeded"):
        client.embed_texts(["hello"])

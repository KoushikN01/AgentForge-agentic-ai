"""
Tests for app.llm.gemini.GeminiClient.

IMPORTANT — what these tests do and don't prove:
These tests mock google.genai.Client entirely, so they verify that
GeminiClient builds the right requests and handles responses/errors
correctly. They do NOT prove that a real call to the live Gemini API
works — that needs a real GEMINI_API_KEY and network access, neither of
which is available in this environment. See BUILD_VERIFICATION.md.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.llm.gemini import GeminiClient, GeminiConfigError, GeminiRequestError


def make_settings(api_key: str | None = "fake-test-key") -> Settings:
    return Settings(
        gemini_api_key=api_key,
        gemini_model="gemini-2.5-flash",
        gemini_embedding_model="gemini-embedding-001",
        database_url="sqlite:///:memory:",
        log_level="INFO",
        rag_mode="vector",
    )


class SampleSchema(BaseModel):
    answer: str
    confidence: float


def test_raises_config_error_when_no_api_key():
    with pytest.raises(GeminiConfigError, match="GEMINI_API_KEY"):
        GeminiClient(config=make_settings(api_key=None))


@patch("app.llm.gemini.genai.Client")
def test_generate_text_returns_response_text(mock_client_cls):
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text="the answer")
    mock_client_cls.return_value = mock_client

    client = GeminiClient(config=make_settings())
    result = client.generate_text("What is 2+2?")

    assert result == "the answer"
    # Check the model name from config was actually used in the call.
    _, kwargs = mock_client.models.generate_content.call_args
    assert kwargs["model"] == "gemini-2.5-flash"
    assert kwargs["contents"] == "What is 2+2?"


@patch("app.llm.gemini.genai.Client")
def test_generate_text_raises_on_empty_response(mock_client_cls):
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text="")
    mock_client_cls.return_value = mock_client

    client = GeminiClient(config=make_settings())

    with pytest.raises(GeminiRequestError, match="empty response"):
        client.generate_text("hello")


@patch("app.llm.gemini.genai.Client")
def test_generate_text_wraps_sdk_errors(mock_client_cls):
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("network exploded")
    mock_client_cls.return_value = mock_client

    client = GeminiClient(config=make_settings())

    with pytest.raises(GeminiRequestError, match="network exploded"):
        client.generate_text("hello")


@patch("app.llm.gemini.genai.Client")
def test_generate_structured_parses_json_into_model(mock_client_cls):
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(
        text='{"answer": "42", "confidence": 0.9}'
    )
    mock_client_cls.return_value = mock_client

    client = GeminiClient(config=make_settings())
    result = client.generate_structured("What is the answer?", SampleSchema)

    assert isinstance(result, SampleSchema)
    assert result.answer == "42"
    assert result.confidence == 0.9

    # Check the request actually asked Gemini for JSON matching our schema.
    _, kwargs = mock_client.models.generate_content.call_args
    assert kwargs["config"].response_mime_type == "application/json"
    assert kwargs["config"].response_schema is SampleSchema


@patch("app.llm.gemini.genai.Client")
def test_generate_structured_raises_on_malformed_json(mock_client_cls):
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text="not valid json")
    mock_client_cls.return_value = mock_client

    client = GeminiClient(config=make_settings())

    with pytest.raises(Exception):  # pydantic.ValidationError / json decode error
        client.generate_structured("hello", SampleSchema)

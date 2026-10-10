"""
Tests for app.core.config.

These need no Gemini API key and no network access — they just check that
environment variables get read into a Settings object correctly.
"""

from app.core.config import load_settings


def test_default_model_when_no_env_var_set(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    result = load_settings()

    assert result.gemini_model == "gemini-2.5-flash"
    assert result.gemini_api_key is None


def test_reads_gemini_api_key_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")

    result = load_settings()

    assert result.gemini_api_key == "test-key-123"


def test_gemini_model_is_overridable(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-pro")

    result = load_settings()

    assert result.gemini_model == "gemini-2.5-pro"


def test_default_embedding_model_when_no_env_var_set(monkeypatch):
    monkeypatch.delenv("GEMINI_EMBEDDING_MODEL", raising=False)

    result = load_settings()

    assert result.gemini_embedding_model == "gemini-embedding-001"


def test_gemini_embedding_model_is_overridable(monkeypatch):
    monkeypatch.setenv("GEMINI_EMBEDDING_MODEL", "some-future-model")

    result = load_settings()

    assert result.gemini_embedding_model == "some-future-model"


def test_log_level_defaults_to_info(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    result = load_settings()

    assert result.log_level == "INFO"


def test_default_database_url_when_no_env_var_set(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    result = load_settings()

    assert result.database_url == "sqlite:///./agentforge.db"


def test_database_url_is_overridable(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/agentforge")

    result = load_settings()

    assert result.database_url == "postgresql://user:pass@localhost/agentforge"


def test_default_rag_mode_is_vector(monkeypatch):
    monkeypatch.delenv("RAG_MODE", raising=False)
    assert load_settings().rag_mode == "vector"


def test_rag_mode_is_overridable(monkeypatch):
    monkeypatch.setenv("RAG_MODE", "keyword")
    assert load_settings().rag_mode == "keyword"


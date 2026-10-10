"""
Central configuration for AgentForge.

Every setting the app needs comes from environment variables, loaded here
in one place. Nothing else in the codebase should call os.environ directly —
if you need a new setting later (DATABASE_URL, VECTOR_DB_PATH, ...), add it
here first.

Phase 1 only needs the Gemini-related settings and logging. More settings
will be added in later phases as new pieces of the system need them.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load variables from a local .env file (if one exists) into the process
# environment. In production you'd normally set real environment variables
# instead of shipping a .env file, but this makes local development easy.
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Typed, read-only view of the app's configuration."""

    gemini_api_key: str | None
    gemini_model: str
    gemini_embedding_model: str
    log_level: str
    database_url: str
    rag_mode: str  # "vector" (agentic RAG, needs Gemini) or "keyword" (free, no LLM)


def load_settings() -> Settings:
    """
    Read configuration from environment variables.

    We deliberately do NOT raise an error here if GEMINI_API_KEY is missing.
    A missing key is only a problem the moment you actually try to call
    Gemini — not when the app starts up or when you import this module.
    That's what lets us import and unit-test everything else (config,
    IncidentState, ...) without needing a real API key at all.
    """
    return Settings(
        gemini_api_key=os.environ.get("GEMINI_API_KEY"),
        # gemini-2.5-flash is the current stable, generally-available Gemini
        # model that's cheap and fast enough for an agentic app that will
        # make many LLM calls. Override it with GEMINI_MODEL if you want to
        # try gemini-2.5-pro or a newer preview model.
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        # gemini-embedding-001 is the current generally-available Gemini
        # text embedding model (its predecessor, text-embedding-004, was
        # deprecated). Override with GEMINI_EMBEDDING_MODEL if needed.
        gemini_embedding_model=os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        # SQLite by default - a single file, zero setup. Point this at a
        # Postgres URL for a production-style database; nothing else in
        # the app needs to change (see app/db/database.py).
        database_url=os.environ.get("DATABASE_URL", "sqlite:///./agentforge.db"),
        # "vector" (default): the Knowledge Agent uses Phase 3's agentic,
        # embeddings-based retrieval, falling back to free keyword search
        # (app/tools/doc_tools.search_docs) only if a Gemini call fails.
        # "keyword": skip embeddings entirely and always use keyword search -
        # useful with no API key, or to keep RAG cost at zero. Either way,
        # retrieval never silently returns nothing because of a transient
        # Gemini failure - see app/agents/knowledge.py.
        rag_mode=os.environ.get("RAG_MODE", "vector"),
    )


# A single shared Settings instance other modules can import directly:
#   from app.core.config import settings
settings = load_settings()

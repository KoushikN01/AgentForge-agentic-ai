"""
Real entrypoint: `uvicorn app.main:app --reload` (from backend/).

Builds the real dependencies (a real GeminiClient - which requires
GEMINI_API_KEY - a real SQLite/Postgres database, and a real ingested
knowledge_base/) once at import time, then builds the app with them via
app.api.app_factory.create_app. Ingesting the knowledge base here means
every request reuses the same in-memory Chroma collection rather than
re-embedding it per request.

This file is intentionally never imported by the test suite - tests use
create_app() directly with stub/test dependencies (see
backend/tests/test_api_incidents.py) so they never need a real API key.
"""

from pathlib import Path

from app.api.app_factory import create_app
from app.core.config import settings
from app.db.database import create_session_factory
from app.llm.gemini import GeminiClient
from app.rag.ingest import ingest_knowledge_base

PROJECT_ROOT = Path(__file__).resolve().parent.parent

gemini_client = GeminiClient()
session_factory = create_session_factory(settings.database_url)
kb_collection = ingest_knowledge_base(PROJECT_ROOT / "knowledge_base", gemini_client)
sample_project_root = PROJECT_ROOT / "sample_project"

app = create_app(
    gemini_client,
    kb_collection,
    sample_project_root,
    session_factory,
    knowledge_base_root=PROJECT_ROOT / "knowledge_base",
    rag_mode=settings.rag_mode,
)

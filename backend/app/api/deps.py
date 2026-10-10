"""
Dependency providers for the API routes.

Everything a route needs (the Gemini client, the ingested knowledge base
collection, the sample project root, and a DB session factory) is
attached to `app.state` once, at app construction time (see
app_factory.create_app) - not built inside each request, and not a
dependency-injection framework: these are plain functions FastAPI calls
via Depends(), each just reading request.app.state.
"""

from pathlib import Path

from fastapi import Request
from sqlalchemy.orm import Session

from app.llm.gemini import GeminiClient


def get_db(request: Request) -> Session:
    with request.app.state.session_factory() as session:
        yield session


def get_gemini_client(request: Request) -> GeminiClient:
    return request.app.state.gemini_client


def get_kb_collection(request: Request):
    return request.app.state.kb_collection


def get_sample_project_root(request: Request) -> Path:
    return request.app.state.sample_project_root


def get_knowledge_base_root(request: Request) -> Path | None:
    return request.app.state.knowledge_base_root


def get_rag_mode(request: Request) -> str:
    return request.app.state.rag_mode

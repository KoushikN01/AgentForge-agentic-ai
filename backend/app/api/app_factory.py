"""
Builds the FastAPI application from already-constructed dependencies.

Kept separate from app/main.py (the real entrypoint) so tests can build
the exact same app wired to a stub GeminiClient, a small test knowledge
base, and an in-memory database - without needing a real API key, real
knowledge_base/, or a real database file. No dependency-injection
framework: this is one plain function.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as incidents_router


def create_app(
    gemini_client,
    kb_collection,
    sample_project_root: Path,
    session_factory,
    knowledge_base_root: Path | None = None,
    rag_mode: str = "vector",
    allowed_origins: list[str] | None = None,
) -> FastAPI:
    app = FastAPI(
        title="AgentForge API",
        description="Multi-agent AI incident investigation platform.",
        version="0.1.0",
    )
    app.state.gemini_client = gemini_client
    app.state.kb_collection = kb_collection
    app.state.sample_project_root = sample_project_root
    app.state.session_factory = session_factory
    app.state.knowledge_base_root = knowledge_base_root
    app.state.rag_mode = rag_mode

    # The React frontend (frontend/) runs on its own dev-server origin
    # (e.g. localhost:5173) and calls this API by URL, so the browser
    # needs CORS permission. Defaults to localhost dev-server ports; pass
    # allowed_origins explicitly for anything else (e.g. a deployed
    # frontend's real URL).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins or ["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(incidents_router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app

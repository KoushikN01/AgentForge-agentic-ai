"""
Tests for the Knowledge Agent's RAG mode and fallback behaviour
(app.agents.knowledge), added in the final completion phase.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.agents.knowledge import build_knowledge_node
from app.llm.gemini import GeminiRequestError
from app.models.incident_state import Incident, IncidentState


@pytest.fixture
def kb_root(tmp_path):
    (tmp_path / "runbook.md").write_text("# Runbook\n\nIf login fails, check JWT_SECRET.\n")
    return tmp_path


def test_keyword_mode_never_calls_gemini(kb_root):
    client = MagicMock()
    node = build_knowledge_node(client, MagicMock(), kb_root, rag_mode="keyword")
    state = IncidentState(incident=Incident(title="Login returns 500", description="JWT_SECRET missing"))

    result = node(state)

    assert any("runbook.md" in c for c in result["knowledge_context"])
    assert "keyword mode" in result["messages"][-1]
    client.generate_structured.assert_not_called()
    client.embed_texts.assert_not_called()


def test_keyword_mode_without_a_root_raises_clear_error():
    node = build_knowledge_node(MagicMock(), MagicMock(), None, rag_mode="keyword")
    with pytest.raises(ValueError, match="knowledge_base_root"):
        node(IncidentState(incident=Incident(title="x", description="y")))


def test_vector_mode_falls_back_to_keyword_when_gemini_fails(kb_root):
    client = MagicMock()
    # agentic_retrieve's first Gemini call is decide_what_to_search()
    # (generate_structured); failing here is what a real quota/auth error
    # looks like, and is what the fallback needs to handle.
    client.generate_structured.side_effect = GeminiRequestError("simulated quota exceeded")
    node = build_knowledge_node(client, MagicMock(), kb_root, rag_mode="vector")
    state = IncidentState(incident=Incident(title="Login returns 500", description="JWT_SECRET missing"))

    result = node(state)

    assert any("runbook.md" in c for c in result["knowledge_context"])
    assert "fell back to keyword search" in result["messages"][-1]


def test_vector_mode_without_fallback_root_propagates_the_error():
    client = MagicMock()
    client.generate_structured.side_effect = GeminiRequestError("simulated quota exceeded")
    node = build_knowledge_node(client, MagicMock(), knowledge_base_root=None, rag_mode="vector")

    with pytest.raises(GeminiRequestError):
        node(IncidentState(incident=Incident(title="x", description="y")))

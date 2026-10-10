"""
Tests for app.rag.agentic_retrieval.

GeminiClient is fully replaced with a MagicMock configured to return
specific RetrievalPlan / SufficiencyCheck objects — this tests the LOOP
LOGIC (stop when sufficient, retry with feedback when not, never exceed
MAX_ROUNDS) without needing a real Gemini call. The vector store is real.
"""

from unittest.mock import MagicMock

from app.rag.agentic_retrieval import MAX_ROUNDS, agentic_retrieve
from app.rag.models import RetrievalPlan, SufficiencyCheck
from app.rag.vector_store import add_chunks, build_collection
from app.rag.models import Chunk


def make_collection():
    collection = build_collection("test_agentic")
    chunks = [
        Chunk(id="runbook::0", source_path="runbook.md", chunk_index=0, text="JWT_SECRET env var info"),
        Chunk(id="incident::0", source_path="incidents/INC-1.md", chunk_index=0, text="past login incident"),
    ]
    add_chunks(collection, chunks, embeddings=[[1.0, 0.0], [0.9, 0.1]])
    return collection


def test_stops_after_one_round_when_sufficient():
    collection = make_collection()
    stub_client = MagicMock()
    stub_client.embed_texts.return_value = [[1.0, 0.0]]
    stub_client.generate_structured.side_effect = [
        RetrievalPlan(queries=["login 500 error"], reasoning="incident mentions login"),
        SufficiencyCheck(is_sufficient=True, reasoning="found the relevant doc"),
    ]

    result = agentic_retrieve(stub_client, collection, "Login endpoint returns 500")

    assert len(result.rounds) == 1
    assert result.stopped_because_sufficient is True
    assert len(result.final_chunks) > 0


def test_runs_second_round_with_feedback_when_first_is_insufficient():
    collection = make_collection()
    stub_client = MagicMock()
    stub_client.embed_texts.return_value = [[1.0, 0.0]]
    stub_client.generate_structured.side_effect = [
        RetrievalPlan(queries=["login error"], reasoning="first guess"),
        SufficiencyCheck(
            is_sufficient=False, reasoning="missing root cause", missing_information="env var details"
        ),
        RetrievalPlan(queries=["environment variable configuration"], reasoning="refined guess"),
        SufficiencyCheck(is_sufficient=True, reasoning="now it's clear"),
    ]

    result = agentic_retrieve(stub_client, collection, "Login endpoint returns 500")

    assert len(result.rounds) == 2
    assert result.rounds[0].sufficiency.is_sufficient is False
    assert result.rounds[1].plan.queries == ["environment variable configuration"]
    assert result.stopped_because_sufficient is True

    # The second round's plan should have been asked for using the first
    # round's missing_information as feedback.
    second_call_prompt = stub_client.generate_structured.call_args_list[2].args[0]
    assert "env var details" in second_call_prompt


def test_never_exceeds_max_rounds_even_if_never_sufficient():
    collection = make_collection()
    stub_client = MagicMock()
    stub_client.embed_texts.return_value = [[1.0, 0.0]]
    stub_client.generate_structured.side_effect = [
        RetrievalPlan(queries=["q1"], reasoning="r1"),
        SufficiencyCheck(is_sufficient=False, reasoning="still missing", missing_information="more info"),
        RetrievalPlan(queries=["q2"], reasoning="r2"),
        SufficiencyCheck(is_sufficient=False, reasoning="still missing", missing_information="more info"),
    ]

    result = agentic_retrieve(stub_client, collection, "Some incident")

    assert len(result.rounds) == MAX_ROUNDS
    assert result.stopped_because_sufficient is False

"""
Per-agent unit tests. Each agent runs against a REAL sandbox copy of
sample_project (real tools, real patching, real pytest where relevant);
only Gemini is mocked.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.agents.coding import build_coding_node
from app.agents.debugging import build_debugging_node
from app.agents.human_approval import apply_human_decision, mark_awaiting_approval, mark_failed
from app.agents.investigation import build_investigation_node
from app.agents.knowledge import build_knowledge_node
from app.agents.review import build_review_node
from app.agents.supervisor import start_investigation
from app.agents.testing import build_testing_node
from app.agents.workspace import create_incident_workspace
from app.models.agent_outputs import (
    EvidenceSummary,
    PatchProposal,
    ReviewResult,
    RootCauseAnalysis,
    TestOutcome,
)
from app.models.incident_state import Incident, IncidentState, IncidentStatus
from app.rag.models import (
    AgenticRetrievalResult,
    Chunk,
    RetrievalPlan,
    RetrievalRound,
    RetrievedChunk,
    SufficiencyCheck,
)

SAMPLE_PROJECT_ROOT = Path(__file__).resolve().parents[2] / "sample_project"

BUG_B_PATCH = PatchProposal(
    target_file="app/orders.py",
    explanation="Apply TAX_RATE to the order subtotal.",
    original_snippet="total = subtotal  # forgot to apply TAX_RATE here",
    replacement_snippet="total = subtotal * (1 + TAX_RATE)",
    relevant_test_path="tests/test_orders.py",
)


@pytest.fixture
def workspace():
    return create_incident_workspace(SAMPLE_PROJECT_ROOT)


def new_state(**kwargs) -> IncidentState:
    return IncidentState(incident=Incident(title="x", description="y"), **kwargs)


# ---- Supervisor ----

def test_supervisor_sets_in_progress():
    result = start_investigation(new_state())
    assert result["incident"].status == IncidentStatus.IN_PROGRESS
    assert "Investigation started" in result["messages"][-1]


# ---- Investigation ----

def test_investigation_gathers_real_log_and_code_evidence(workspace):
    client = MagicMock()
    client.generate_structured.return_value = EvidenceSummary(summary="env var problem", key_findings=["f1", "f2"])
    node = build_investigation_node(client, workspace)

    result = node(new_state())

    assert any("KeyError" in e for e in result["evidence"])
    assert any("app/auth.py" in e for e in result["evidence"])
    assert "finding: f1" in result["messages"]
    client.generate_structured.assert_called_once()


# ---- Knowledge ----

@patch("app.agents.knowledge.agentic_retrieve")
def test_knowledge_wraps_retrieval_result(mock_retrieve):
    chunk = Chunk(id="runbook.md::0", source_path="runbook.md", chunk_index=0, text="JWT_SECRET info")
    retrieved = RetrievedChunk(chunk=chunk, distance=0.1)
    mock_retrieve.return_value = AgenticRetrievalResult(
        rounds=[
            RetrievalRound(
                round_number=1,
                plan=RetrievalPlan(queries=["q"], reasoning="r"),
                retrieved=[retrieved],
                sufficiency=SufficiencyCheck(is_sufficient=True, reasoning="ok"),
            )
        ],
        final_chunks=[retrieved],
    )

    result = build_knowledge_node(MagicMock(), MagicMock())(new_state())

    assert result["knowledge_context"] == ["runbook.md: JWT_SECRET info"]
    assert "sufficient=True" in result["messages"][-1]


# ---- Debugging ----

def test_debugging_returns_diagnosis_and_grounds_prompt_in_evidence():
    client = MagicMock()
    client.generate_structured.return_value = RootCauseAnalysis(
        root_cause="Wrong env var name", confidence=0.9, supporting_evidence=["app/auth.py:39"]
    )
    state = new_state(evidence=["logs: KeyError: 'JWT_SECRET_KEY'"], knowledge_context=["deploy notes: JWT_SECRET"])

    result = build_debugging_node(client)(state)

    assert result["root_cause"].root_cause == "Wrong env var name"
    assert "confidence 0.90" in result["messages"][-1]
    prompt = client.generate_structured.call_args.args[0]
    assert "KeyError" in prompt and "deploy notes" in prompt


# ---- Coding ----

def test_coding_patches_the_sandbox_only(workspace):
    client = MagicMock()
    client.generate_structured.return_value = BUG_B_PATCH

    result = build_coding_node(client, workspace)(new_state())

    assert result["retry_count"] == 0
    assert "total = subtotal * (1 + TAX_RATE)" in (workspace / "app" / "orders.py").read_text()
    assert "forgot to apply TAX_RATE" in (SAMPLE_PROJECT_ROOT / "app" / "orders.py").read_text()


def test_coding_survives_a_patch_that_does_not_apply(workspace):
    client = MagicMock()
    client.generate_structured.return_value = BUG_B_PATCH.model_copy(update={"original_snippet": "nope"})

    result = build_coding_node(client, workspace)(new_state())

    assert any("could not apply" in m for m in result["messages"])


def test_coding_treats_existing_test_result_as_a_retry_and_uses_feedback(workspace):
    client = MagicMock()
    client.generate_structured.return_value = BUG_B_PATCH
    state = new_state(
        test_result=TestOutcome(passed=3, failed=1, all_passed=False, summary="3 passed, 1 failed"),
        review_result=ReviewResult(approved=False, risk_level="low", concerns=["still broken"], reasoning="r"),
    )

    result = build_coding_node(client, workspace)(state)

    assert result["retry_count"] == 1
    assert "3 passed, 1 failed" in result["retry_feedback"]
    assert "previous fix attempt did not work" in client.generate_structured.call_args.args[0].lower()


# ---- Testing (real pytest) ----

def test_testing_reports_the_known_buggy_state(workspace):
    result = build_testing_node(workspace)(new_state())
    assert (result["test_result"].passed, result["test_result"].failed) == (4, 3)
    assert result["test_result"].all_passed is False


# ---- Review ----

def test_review_prompt_contains_real_diff_and_test_results(workspace):
    coding_client = MagicMock()
    coding_client.generate_structured.return_value = BUG_B_PATCH
    coded = build_coding_node(coding_client, workspace)(new_state())
    state = new_state(
        patch_proposal=coded["patch_proposal"],
        test_result=TestOutcome(passed=7, failed=0, all_passed=True, summary="7 passed, 0 failed"),
    )
    review_client = MagicMock()
    review_client.generate_structured.return_value = ReviewResult(
        approved=True, risk_level="low", concerns=[], reasoning="scoped"
    )

    result = build_review_node(review_client, SAMPLE_PROJECT_ROOT, workspace)(state)

    assert result["review_result"].approved is True
    prompt = review_client.generate_structured.call_args.args[0]
    assert "+    total = subtotal * (1 + TAX_RATE)" in prompt
    assert "7 passed, 0 failed" in prompt


def test_review_without_a_patch_rejects_safely():
    result = build_review_node(MagicMock(), SAMPLE_PROJECT_ROOT, SAMPLE_PROJECT_ROOT)(new_state())
    assert result["review_result"].approved is False


# ---- Human approval ----

def test_terminal_nodes_set_status():
    assert mark_awaiting_approval(new_state())["incident"].status == IncidentStatus.AWAITING_APPROVAL
    failed = mark_failed(new_state(retry_count=2))
    assert failed["incident"].status == IncidentStatus.FAILED
    assert "2 retry" in failed["messages"][-1]


@pytest.fixture
def real_and_workspace(tmp_path):
    real, ws = tmp_path / "real", tmp_path / "ws"
    for root in (real, ws):
        (root / "app").mkdir(parents=True)
    (real / "app" / "orders.py").write_text("bug\n")
    (ws / "app" / "orders.py").write_text("fixed\n")
    return real, ws


def test_approval_copies_fix_into_real_project(real_and_workspace):
    real, ws = real_and_workspace
    state = new_state(patch_proposal=BUG_B_PATCH)
    result = apply_human_decision(state, real, ws, approved=True)
    assert result.incident.status == IncidentStatus.RESOLVED
    assert (real / "app" / "orders.py").read_text() == "fixed\n"


def test_rejection_leaves_real_project_untouched(real_and_workspace):
    real, ws = real_and_workspace
    result = apply_human_decision(new_state(patch_proposal=BUG_B_PATCH), real, ws, approved=False)
    assert result.incident.status == IncidentStatus.FAILED
    assert (real / "app" / "orders.py").read_text() == "bug\n"


def test_approval_without_a_patch_raises(real_and_workspace):
    real, ws = real_and_workspace
    with pytest.raises(ValueError, match="no patch_proposal"):
        apply_human_decision(new_state(), real, ws, approved=True)

"""
Integration tests for the COMPILED LangGraph workflow (app/graph/workflow.py).

The per-agent tests elsewhere check each node in isolation. These check
the thing only the graph itself does: routing. We stream the compiled
graph and record which nodes actually ran, in order, so the tests prove
supervisor -> investigation -> knowledge -> debugging -> coding -> testing
-> review -> (awaiting_approval | back to coding | failed) really happens.

What is real: the LangGraph graph, all agent code, the log/repo/doc tools,
the sandbox workspace, patch application, and REAL pytest runs against the
sandbox copy of sample_project. What is scripted: Gemini. The fake client
below returns canned structured answers (a correct patch, a bad patch, a
review that approves only when tests really passed). This proves the
plumbing and routing; it does NOT prove real Gemini writes good patches.
"""

import shutil
from pathlib import Path

import pytest
from unittest.mock import MagicMock

from app.agents.human_approval import apply_human_decision
from app.agents.workspace import create_incident_workspace
from app.graph.workflow import MAX_RETRIES, build_graph
from app.models.agent_outputs import (
    EvidenceSummary,
    PatchProposal,
    ReviewResult,
    RootCauseAnalysis,
)
from app.models.incident_state import Incident, IncidentState, IncidentStatus
from app.rag.models import Chunk, RetrievalPlan, SufficiencyCheck
from app.rag.vector_store import add_chunks, build_collection
from app.tools.test_tools import run_tests

SHIPPED_SAMPLE_PROJECT = Path(__file__).resolve().parents[2] / "sample_project"

GOOD_PATCH = PatchProposal(
    target_file="app/orders.py",
    explanation="Apply TAX_RATE to the subtotal.",
    original_snippet="total = subtotal  # forgot to apply TAX_RATE here",
    replacement_snippet="total = subtotal * (1 + TAX_RATE)",
    relevant_test_path="tests/test_orders.py",
)
BAD_PATCH = PatchProposal(
    target_file="app/orders.py",
    explanation="A wrong guess whose snippet does not exist in the file.",
    original_snippet="this snippet is not in the file",
    replacement_snippet="whatever",
    relevant_test_path="tests/test_orders.py",
)


def make_scripted_gemini(patches: list[PatchProposal]):
    """A fake GeminiClient that answers each structured request by type."""
    patch_iter = iter(patches)
    client = MagicMock()
    client.embed_texts.return_value = [[1.0, 0.0]]

    def fake_generate_structured(prompt, response_model=None, system_instruction=None):
        if response_model is RetrievalPlan:
            return RetrievalPlan(queries=["order total tax"], reasoning="scripted")
        if response_model is SufficiencyCheck:
            return SufficiencyCheck(is_sufficient=True, reasoning="scripted")
        if response_model is EvidenceSummary:
            return EvidenceSummary(summary="scripted summary", key_findings=["scripted finding"])
        if response_model is RootCauseAnalysis:
            return RootCauseAnalysis(
                root_cause="Sales tax is never applied to the order total",
                confidence=0.9,
                supporting_evidence=["app/orders.py"],
            )
        if response_model is PatchProposal:
            return next(patch_iter)
        if response_model is ReviewResult:
            # Reactive fake: approve only if the real test run had 0 failures.
            tests_ok = ", 0 failed" in prompt
            return ReviewResult(
                approved=tests_ok,
                risk_level="low",
                concerns=[] if tests_ok else ["Tests still failing"],
                reasoning="scripted review",
            )
        raise AssertionError(f"Unexpected response_model: {response_model}")

    client.generate_structured.side_effect = fake_generate_structured
    return client


def make_knowledge_collection():
    collection = build_collection("graph_integration")
    chunks = [
        Chunk(id="t::0", source_path="troubleshooting_guide.md", chunk_index=0, text="tax not applied"),
        Chunk(id="a::0", source_path="architecture.md", chunk_index=0, text="orders total"),
    ]
    add_chunks(collection, chunks, embeddings=[[1.0, 0.0], [0.9, 0.1]])
    return collection


@pytest.fixture
def project_copy(tmp_path):
    """A throwaway stand-in for the 'real' project with only Bug B left,
    so one correct patch makes the whole suite pass."""
    real = tmp_path / "real_project"
    shutil.copytree(SHIPPED_SAMPLE_PROJECT, real, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    auth = real / "app" / "auth.py"
    auth.write_text(auth.read_text().replace("JWT_SECRET_KEY", "JWT_SECRET"))  # fix Bug A
    orders = real / "app" / "orders.py"
    orders.write_text(
        orders.read_text().replace(
            "    order = ORDERS[order_id]",
            "    try:\n        order = ORDERS[order_id]\n    except KeyError:\n        raise OrderNotFoundError(order_id)",
        )
    )  # fix Bug C
    return real


def run_graph(real_root: Path, patches: list[PatchProposal]):
    workspace = create_incident_workspace(real_root)
    client = make_scripted_gemini(patches)
    graph = build_graph(client, make_knowledge_collection(), real_root, workspace)
    initial = IncidentState(
        incident=Incident(title="Order total is wrong", description="GET /api/orders/101 returns 45.00, expected 48.60")
    )

    visited: list[str] = []
    final: dict = {}
    for update in graph.stream(initial, stream_mode="updates"):
        for node_name, node_update in update.items():
            visited.append(node_name)
            final.update(node_update)
    # stream "updates" only carries changed keys; rebuild a full state by invoking-equivalent merge
    state = initial.model_copy(update=final)
    return state, visited, workspace, client


def test_happy_path_routes_through_every_agent_to_awaiting_approval(project_copy):
    state, visited, workspace, client = run_graph(project_copy, [GOOD_PATCH])

    assert visited == [
        "supervisor", "investigation", "knowledge", "debugging",
        "coding", "testing", "review", "awaiting_approval",
    ]
    assert state.incident.status == IncidentStatus.AWAITING_APPROVAL
    assert state.test_result.all_passed is True
    assert state.review_result.approved is True
    assert state.retry_count == 0
    assert state.root_cause.confidence == 0.9
    assert len(state.evidence) > 0
    assert len(state.knowledge_context) > 0


def test_happy_path_patches_only_the_sandbox_before_approval(project_copy):
    before = (project_copy / "app" / "orders.py").read_text()

    state, _, workspace, _ = run_graph(project_copy, [GOOD_PATCH])

    assert (project_copy / "app" / "orders.py").read_text() == before  # real project untouched
    assert "total = subtotal * (1 + TAX_RATE)" in (workspace / "app" / "orders.py").read_text()


def test_approval_applies_fix_to_real_project_and_its_tests_then_pass(project_copy):
    state, _, workspace, _ = run_graph(project_copy, [GOOD_PATCH])
    assert run_tests(project_copy).all_passed is False  # still buggy before approval

    resolved = apply_human_decision(state, project_copy, workspace, approved=True)

    assert resolved.incident.status == IncidentStatus.RESOLVED
    assert run_tests(project_copy).all_passed is True


def test_rejection_leaves_real_project_untouched(project_copy):
    state, _, workspace, _ = run_graph(project_copy, [GOOD_PATCH])
    before = (project_copy / "app" / "orders.py").read_text()

    rejected = apply_human_decision(state, project_copy, workspace, approved=False)

    assert rejected.incident.status == IncidentStatus.FAILED
    assert (project_copy / "app" / "orders.py").read_text() == before


def test_retry_path_loops_back_to_coding_then_succeeds(project_copy):
    state, visited, _, client = run_graph(project_copy, [BAD_PATCH, GOOD_PATCH])

    assert visited == [
        "supervisor", "investigation", "knowledge", "debugging",
        "coding", "testing", "review",
        "coding", "testing", "review",
        "awaiting_approval",
    ]
    assert state.retry_count == 1
    assert state.incident.status == IncidentStatus.AWAITING_APPROVAL
    assert state.test_result.all_passed is True
    # the second coding prompt carried reflection feedback from the first failure
    coding_prompts = [
        c.args[0] for c in client.generate_structured.call_args_list
        if c.kwargs.get("response_model") is PatchProposal
    ]
    assert len(coding_prompts) == 2
    assert "previous fix attempt did not work" in coding_prompts[1].lower()


def test_retries_are_bounded_and_end_in_failed(project_copy):
    patches = [BAD_PATCH] * (MAX_RETRIES + 1)

    state, visited, _, _ = run_graph(project_copy, patches)

    assert visited.count("coding") == MAX_RETRIES + 1
    assert visited[-1] == "failed"
    assert "awaiting_approval" not in visited
    assert state.incident.status == IncidentStatus.FAILED
    assert state.retry_count == MAX_RETRIES


def test_running_the_graph_never_modifies_the_shipped_sample_project():
    shipped_files = {p: p.read_text() for p in SHIPPED_SAMPLE_PROJECT.rglob("*.py")}

    # The shipped project has all 3 bugs, so one good patch can't make the
    # suite pass: the graph will retry until retries run out. Supply enough
    # patches for every attempt.
    state, visited, _, _ = run_graph(SHIPPED_SAMPLE_PROJECT, [GOOD_PATCH] + [BAD_PATCH] * MAX_RETRIES)

    assert visited[-1] == "failed"
    for path, content in shipped_files.items():
        assert path.read_text() == content

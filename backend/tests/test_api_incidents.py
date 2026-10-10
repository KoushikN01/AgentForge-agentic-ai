"""
End-to-end tests for the Phase 5 API, using FastAPI's TestClient against
the REAL app (app_factory.create_app), a REAL in-memory database, and a
REAL sandbox workspace/sample_project copy. Only Gemini is scripted -
same fake-client pattern as test_graph_integration.py.

The background task started by POST /investigate has, by the time
client.post() returns, already run to completion - Starlette's TestClient
runs background tasks synchronously as part of the request/response
cycle, which these tests confirm by polling immediately with no sleep.
"""

import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.app_factory import create_app
from app.db.database import create_session_factory
from app.models.agent_outputs import EvidenceSummary, PatchProposal, ReviewResult, RootCauseAnalysis
from app.rag.models import RetrievalPlan, SufficiencyCheck
from app.rag.vector_store import add_chunks, build_collection
from app.rag.models import Chunk

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
    explanation="wrong guess",
    original_snippet="this text is not in the file",
    replacement_snippet="whatever",
    relevant_test_path="tests/test_orders.py",
)


def make_scripted_gemini(patches: list[PatchProposal]):
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
            tests_ok = ", 0 failed" in prompt
            return ReviewResult(
                approved=tests_ok, risk_level="low",
                concerns=[] if tests_ok else ["Tests still failing"], reasoning="scripted review",
            )
        raise AssertionError(f"Unexpected response_model: {response_model}")

    client.generate_structured.side_effect = fake_generate_structured
    return client


def make_kb_collection():
    collection = build_collection("api_test_kb")
    chunks = [Chunk(id="t::0", source_path="troubleshooting_guide.md", chunk_index=0, text="tax not applied")]
    add_chunks(collection, chunks, embeddings=[[1.0, 0.0]])
    return collection


@pytest.fixture
def project_copy(tmp_path):
    """Bug B only (tax) left in this copy, so one good patch clears the suite."""
    real = tmp_path / "real_project"
    shutil.copytree(SHIPPED_SAMPLE_PROJECT, real, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    (real / "app" / "auth.py").write_text((real / "app" / "auth.py").read_text().replace("JWT_SECRET_KEY", "JWT_SECRET"))
    orders = real / "app" / "orders.py"
    orders.write_text(
        orders.read_text().replace(
            "    order = ORDERS[order_id]",
            "    try:\n        order = ORDERS[order_id]\n    except KeyError:\n        raise OrderNotFoundError(order_id)",
        )
    )
    return real


def make_client(project_copy: Path, patches: list[PatchProposal]) -> TestClient:
    app = create_app(
        gemini_client=make_scripted_gemini(patches),
        kb_collection=make_kb_collection(),
        sample_project_root=project_copy,
        session_factory=create_session_factory("sqlite:///:memory:"),
    )
    return TestClient(app)


def test_health_check():
    client = make_client(SHIPPED_SAMPLE_PROJECT, [GOOD_PATCH])
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_full_happy_path_create_investigate_approve(project_copy):
    client = make_client(project_copy, [GOOD_PATCH])

    created = client.post(
        "/incidents",
        json={"title": "Order total is wrong", "description": "GET /api/orders/101 returns 45.00, expected 48.60"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "new"
    incident_id = body["id"]

    started = client.post(f"/incidents/{incident_id}/investigate")
    assert started.status_code == 200
    # By the time this call returns, TestClient has already run the background task.
    assert started.json()["status"] in ("in_progress", "awaiting_approval")

    state = client.get(f"/incidents/{incident_id}").json()
    assert state["incident"]["status"] == "awaiting_approval"
    assert state["test_result"]["all_passed"] is True
    assert state["review_result"]["approved"] is True

    evidence = client.get(f"/incidents/{incident_id}/evidence")
    assert evidence.status_code == 200
    assert len(evidence.json()) > 0

    patch = client.get(f"/incidents/{incident_id}/patch")
    assert patch.status_code == 200
    assert patch.json()["target_file"] == "app/orders.py"

    before = (project_copy / "app" / "orders.py").read_text()
    approved = client.post(f"/incidents/{incident_id}/approve", json={"approved": True})
    assert approved.status_code == 200
    report = approved.json()
    assert report["status"] == "resolved"
    assert report["review_approved"] is True
    after = (project_copy / "app" / "orders.py").read_text()
    assert before != after
    assert "total = subtotal * (1 + TAX_RATE)" in after

    final_report = client.get(f"/incidents/{incident_id}/report").json()
    assert final_report["status"] == "resolved"


def test_rejecting_leaves_real_project_untouched(project_copy):
    client = make_client(project_copy, [GOOD_PATCH])
    incident_id = client.post("/incidents", json={"title": "x", "description": "y"}).json()["id"]
    client.post(f"/incidents/{incident_id}/investigate")
    before = (project_copy / "app" / "orders.py").read_text()

    rejected = client.post(f"/incidents/{incident_id}/approve", json={"approved": False})

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "failed"
    assert (project_copy / "app" / "orders.py").read_text() == before


def test_retry_path_via_api_reaches_awaiting_approval(project_copy):
    client = make_client(project_copy, [BAD_PATCH, GOOD_PATCH])
    incident_id = client.post("/incidents", json={"title": "x", "description": "y"}).json()["id"]

    client.post(f"/incidents/{incident_id}/investigate")

    state = client.get(f"/incidents/{incident_id}").json()
    assert state["incident"]["status"] == "awaiting_approval"
    assert state["retry_count"] == 1


def test_cannot_investigate_twice(project_copy):
    client = make_client(project_copy, [GOOD_PATCH, GOOD_PATCH])
    incident_id = client.post("/incidents", json={"title": "x", "description": "y"}).json()["id"]
    client.post(f"/incidents/{incident_id}/investigate")

    second = client.post(f"/incidents/{incident_id}/investigate")

    assert second.status_code == 409


def test_cannot_approve_before_awaiting_approval(project_copy):
    client = make_client(project_copy, [GOOD_PATCH])
    incident_id = client.post("/incidents", json={"title": "x", "description": "y"}).json()["id"]

    response = client.post(f"/incidents/{incident_id}/approve", json={"approved": True})

    assert response.status_code == 409


def test_404_for_unknown_incident(project_copy):
    client = make_client(project_copy, [GOOD_PATCH])
    assert client.get("/incidents/does-not-exist").status_code == 404
    assert client.get("/incidents/does-not-exist/evidence").status_code == 404
    assert client.post("/incidents/does-not-exist/investigate").status_code == 404


def test_patch_endpoint_404s_before_a_patch_exists(project_copy):
    client = make_client(project_copy, [GOOD_PATCH])
    incident_id = client.post("/incidents", json={"title": "x", "description": "y"}).json()["id"]

    assert client.get(f"/incidents/{incident_id}/patch").status_code == 404


def test_list_incidents_returns_created_incidents(project_copy):
    client = make_client(project_copy, [GOOD_PATCH])
    client.post("/incidents", json={"title": "one", "description": "y"})
    client.post("/incidents", json={"title": "two", "description": "y"})

    response = client.get("/incidents")

    assert response.status_code == 200
    titles = {row["title"] for row in response.json()}
    assert titles == {"one", "two"}


def test_timeline_reports_one_completed_event_per_node(project_copy):
    client = make_client(project_copy, [GOOD_PATCH])
    incident_id = client.post("/incidents", json={"title": "x", "description": "y"}).json()["id"]
    client.post(f"/incidents/{incident_id}/investigate")

    timeline = client.get(f"/incidents/{incident_id}/timeline")

    assert timeline.status_code == 200
    nodes = [e["node"] for e in timeline.json()]
    # The happy-path graph genuinely runs a terminal "awaiting_approval" node
    # after "review" (see app/graph/workflow.py and
    # test_graph_integration.py's test_happy_path_routes_through_every_agent_to_awaiting_approval,
    # true since Phase 4) - so the real, correct timeline has 8 entries, not 7.
    assert nodes == [
        "supervisor", "investigation", "knowledge", "debugging", "coding", "testing", "review", "awaiting_approval",
    ]
    assert all(e["status"] == "completed" for e in timeline.json())
    assert all(isinstance(e["duration_ms"], (int, float)) for e in timeline.json())


def test_reject_endpoint_is_equivalent_to_approve_false(project_copy):
    client = make_client(project_copy, [GOOD_PATCH])
    incident_id = client.post("/incidents", json={"title": "x", "description": "y"}).json()["id"]
    client.post(f"/incidents/{incident_id}/investigate")
    before = (project_copy / "app" / "orders.py").read_text()

    rejected = client.post(f"/incidents/{incident_id}/reject")

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "failed"
    assert (project_copy / "app" / "orders.py").read_text() == before


def test_workspace_path_is_persisted_and_sandbox_cleaned_up_after_approval(project_copy):
    client = make_client(project_copy, [GOOD_PATCH])
    incident_id = client.post("/incidents", json={"title": "x", "description": "y"}).json()["id"]
    client.post(f"/incidents/{incident_id}/investigate")

    state = client.get(f"/incidents/{incident_id}").json()
    workspace_path = Path(state["workspace_path"])
    assert workspace_path.exists()  # still there - approval hasn't happened yet

    client.post(f"/incidents/{incident_id}/approve", json={"approved": True})

    assert not workspace_path.exists()  # cleaned up now that the decision is made


def test_sandbox_is_cleaned_up_immediately_when_retries_are_exhausted(project_copy):
    client = make_client(project_copy, [BAD_PATCH, BAD_PATCH, BAD_PATCH])
    incident_id = client.post("/incidents", json={"title": "x", "description": "y"}).json()["id"]

    client.post(f"/incidents/{incident_id}/investigate")

    state = client.get(f"/incidents/{incident_id}").json()
    assert state["incident"]["status"] == "failed"
    assert not Path(state["workspace_path"]).exists()


def test_cors_allows_the_default_frontend_dev_origin(project_copy):
    client = make_client(project_copy, [GOOD_PATCH])
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_investigation_that_crashes_is_recorded_as_failed_not_lost(project_copy):
    client = make_client(project_copy, [GOOD_PATCH])
    # Force a real crash inside the workflow by making the scripted client
    # blow up instead of returning a structured response.
    client.app.state.gemini_client.generate_structured.side_effect = RuntimeError("simulated Gemini outage")
    incident_id = client.post("/incidents", json={"title": "x", "description": "y"}).json()["id"]

    client.post(f"/incidents/{incident_id}/investigate")

    state = client.get(f"/incidents/{incident_id}").json()
    assert state["incident"]["status"] == "failed"
    assert any("crashed" in m for m in state["messages"])

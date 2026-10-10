"""
Evaluation harness.

Runs the full multi-agent workflow (Phase 4/5) against every real incident
this project actually has, and reports measured results: did the Coding
Agent target the right file, did the sandbox tests end up passing, how
many retries did it take, how long did it take.

IMPORTANT - about the incident count: sample_project has exactly THREE
real, distinct bugs (see docs/sample-project-bugs.md). This harness
evaluates three incidents - one per real bug - rather than padding the
count to "10-20" with incidents that don't correspond to anything actually
broken in the codebase. Evaluating against bugs that don't exist would
produce numbers that look thorough but mean nothing; this project's own
rules explicitly forbid fabricated benchmark numbers.

Gemini usage:
  - No GEMINI_API_KEY in the environment -> runs with a SCRIPTED Gemini
    client (same fake-response pattern used throughout the test suite)
    and labels every result "mock". This still exercises the real graph,
    real tools, real sandbox, and real pytest runs - everything except
    actual Gemini reasoning.
  - A real GEMINI_API_KEY -> runs against the live Gemini API and labels
    results "live". Root-cause/patch QUALITY with live Gemini is then
    genuinely measured, not scripted.

Usage:
    python evaluation/run_evaluation.py
"""

import importlib.util
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.agents.workspace import create_incident_workspace  # noqa: E402
from app.graph.workflow import MAX_RETRIES, build_graph  # noqa: E402
from app.llm.gemini import GeminiClient, GeminiConfigError  # noqa: E402
from app.models.agent_outputs import (  # noqa: E402
    EvidenceSummary,
    PatchProposal,
    ReviewResult,
    RootCauseAnalysis,
)
from app.models.incident_state import Incident, IncidentState, IncidentStatus  # noqa: E402
from app.rag.ingest import ingest_knowledge_base  # noqa: E402
from app.rag.models import RetrievalPlan, SufficiencyCheck  # noqa: E402

# Reuse the demo script's incident definitions and bug-isolation logic
# instead of duplicating them - see scripts/investigate_demo.py.
_spec = importlib.util.spec_from_file_location(
    "investigate_demo", PROJECT_ROOT / "scripts" / "investigate_demo.py"
)
demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(demo)

# The correct patch for each real bug - used both to drive the scripted
# Gemini client (mock mode) and to judge correctness (both modes): a
# patch is scored "correct" if it targets the same file as the real fix,
# regardless of which mode produced it.
_CORRECT_PATCHES: dict[str, PatchProposal] = {
    "login": PatchProposal(
        target_file="app/auth.py",
        explanation="Use the documented JWT_SECRET variable name.",
        original_snippet='os.environ["JWT_SECRET_KEY"]',
        replacement_snippet='os.environ["JWT_SECRET"]',
        relevant_test_path="tests/test_auth.py",
    ),
    "orders-total": PatchProposal(
        target_file="app/orders.py",
        explanation="Apply TAX_RATE to the subtotal.",
        original_snippet="total = subtotal  # forgot to apply TAX_RATE here",
        replacement_snippet="total = subtotal * (1 + TAX_RATE)",
        relevant_test_path="tests/test_orders.py",
    ),
    "orders-404": PatchProposal(
        target_file="app/orders.py",
        explanation="Raise OrderNotFoundError instead of letting KeyError propagate.",
        original_snippet="    order = ORDERS[order_id]",
        replacement_snippet=(
            "    try:\n        order = ORDERS[order_id]\n"
            "    except KeyError:\n        raise OrderNotFoundError(order_id)"
        ),
        relevant_test_path="tests/test_orders.py",
    ),
}


def make_scripted_gemini(incident_key: str) -> GeminiClient:
    """A fake client that proposes the correct patch on the first try."""
    client = MagicMock()
    client.embed_texts.side_effect = lambda texts, task_type="RETRIEVAL_DOCUMENT": [[1.0, 0.0] for _ in texts]
    correct_patch = _CORRECT_PATCHES[incident_key]

    def fake_generate_structured(prompt, response_model=None, system_instruction=None):
        if response_model is RetrievalPlan:
            return RetrievalPlan(queries=[incident_key], reasoning="scripted")
        if response_model is SufficiencyCheck:
            return SufficiencyCheck(is_sufficient=True, reasoning="scripted")
        if response_model is EvidenceSummary:
            return EvidenceSummary(summary="scripted", key_findings=["scripted finding"])
        if response_model is RootCauseAnalysis:
            return RootCauseAnalysis(
                root_cause=f"Root cause for {incident_key}", confidence=0.9, supporting_evidence=["scripted"]
            )
        if response_model is PatchProposal:
            return correct_patch
        if response_model is ReviewResult:
            tests_ok = ", 0 failed" in prompt
            return ReviewResult(approved=tests_ok, risk_level="low", concerns=[], reasoning="scripted")
        raise AssertionError(f"Unexpected response_model: {response_model}")

    client.generate_structured.side_effect = fake_generate_structured
    return client


@dataclass
class EvalResult:
    incident_key: str
    mode: str  # "live" or "mock"
    final_status: str
    root_cause_file_correct: bool | None
    tests_passed: bool | None
    retries_used: int
    execution_seconds: float
    error: str | None = None


def run_one(incident_key: str, live_client: GeminiClient | None) -> EvalResult:
    title, description = demo.INCIDENTS[incident_key]
    project = demo.prepare_demo_project(incident_key)
    workspace = create_incident_workspace(project)

    client = live_client or make_scripted_gemini(incident_key)
    mode = "live" if live_client else "mock"

    start = time.monotonic()
    try:
        collection = ingest_knowledge_base(PROJECT_ROOT / "knowledge_base", client)
        graph = build_graph(client, collection, project, workspace)
        initial = IncidentState(incident=Incident(title=title, description=description))
        result = graph.invoke(initial)
        state = IncidentState.model_validate(result)
        elapsed = time.monotonic() - start

        target_correct = (
            state.patch_proposal is not None
            and state.patch_proposal.target_file == _CORRECT_PATCHES[incident_key].target_file
        )
        return EvalResult(
            incident_key=incident_key,
            mode=mode,
            final_status=state.incident.status.value,
            root_cause_file_correct=target_correct,
            tests_passed=state.test_result.all_passed if state.test_result else None,
            retries_used=state.retry_count,
            execution_seconds=round(elapsed, 2),
        )
    except Exception as exc:  # noqa: BLE001 - record the failure, don't hide it
        return EvalResult(
            incident_key=incident_key,
            mode=mode,
            final_status="error",
            root_cause_file_correct=None,
            tests_passed=None,
            retries_used=0,
            execution_seconds=round(time.monotonic() - start, 2),
            error=str(exc),
        )


def main() -> None:
    try:
        live_client = GeminiClient()
        print("GEMINI_API_KEY found - evaluating against the LIVE Gemini API.\n")
    except GeminiConfigError:
        live_client = None
        print(
            "No GEMINI_API_KEY set - evaluating with a SCRIPTED Gemini client.\n"
            "This measures the graph/tools/sandbox/testing pipeline, NOT real Gemini quality.\n"
        )

    results = [run_one(key, live_client) for key in demo.INCIDENTS]

    print(f"{'incident':<14} {'mode':<5} {'status':<18} {'file ok':<8} {'tests ok':<9} {'retries':<8} {'seconds'}")
    for r in results:
        print(
            f"{r.incident_key:<14} {r.mode:<5} {r.final_status:<18} "
            f"{str(r.root_cause_file_correct):<8} {str(r.tests_passed):<9} {r.retries_used:<8} {r.execution_seconds}"
        )
        if r.error:
            print(f"  error: {r.error}")

    n = len(results)
    resolved_eligible = sum(1 for r in results if r.final_status in ("awaiting_approval", "resolved"))
    correct_file = sum(1 for r in results if r.root_cause_file_correct)
    tests_passed = sum(1 for r in results if r.tests_passed)
    total_retries = sum(r.retries_used for r in results)

    print(f"\n{resolved_eligible}/{n} reached awaiting_approval or resolved")
    print(f"{correct_file}/{n} proposed a patch targeting the correct file")
    print(f"{tests_passed}/{n} ended with the sandbox test suite fully passing")
    print(f"{total_retries} total retries used across all {n} incidents")

    output_dir = PROJECT_ROOT / "evaluation" / "results"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{results[0].mode}_run.json"
    output_path.write_text(json.dumps([asdict(r) for r in results], indent=2))
    print(f"\nFull results written to {output_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()

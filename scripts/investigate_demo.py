"""
End-to-end demo: run the full multi-agent LangGraph workflow against a
real Gemini API, then ask YOU whether to approve the proposed fix.

Requires GEMINI_API_KEY in your .env file. This makes real (small, cheap)
Gemini calls and has NOT been run in the environment this project was
built in, because no API key was available there - see BUILD_VERIFICATION.md.

Safety:
  * The demo copies sample_project/ into a throwaway "demo project" first.
    Everything below - including your approval - only ever touches that copy,
    so your shipped, intentionally-buggy sample_project/ is never modified.
  * Agents patch a second sandbox copy. Nothing reaches the demo project
    until you type "y". There is no auto-approve option, and if there is
    no interactive terminal the fix is NOT applied.

The shipped sample_project has three bugs, and a Coding Agent proposes ONE
find-and-replace patch at a time. To give the demo a clean, single-incident
story, the other two bugs are pre-fixed in the demo copy (this is printed
so it isn't hidden).

Usage (from the project root, virtualenv active):
    python scripts/investigate_demo.py                  # login 500 incident
    python scripts/investigate_demo.py --incident orders-total
    python scripts/investigate_demo.py --incident orders-404
"""

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.agents.human_approval import apply_human_decision  # noqa: E402
from app.agents.workspace import create_incident_workspace  # noqa: E402
from app.graph.workflow import build_graph  # noqa: E402
from app.llm.gemini import GeminiClient, GeminiConfigError, GeminiRequestError  # noqa: E402
from app.models.incident_state import Incident, IncidentState, IncidentStatus  # noqa: E402
from app.rag.ingest import ingest_knowledge_base  # noqa: E402
from app.tools.test_tools import run_tests  # noqa: E402

# Each incident: the report a developer would file, and which bug it is.
INCIDENTS = {
    "login": (
        "Login endpoint returns 500",
        "POST /api/auth/login is returning HTTP 500 for valid users after yesterday's deployment.",
    ),
    "orders-total": (
        "Order total is wrong",
        "GET /api/orders/101 returns a total of 45.00 but the customer was charged 48.60 with tax.",
    ),
    "orders-404": (
        "Unknown order returns 500",
        "GET /api/orders/999999 returns HTTP 500 instead of 404 for an order that doesn't exist.",
    ),
}

# Exact fixes for each bug, used ONLY to pre-fix the bugs this incident is
# not about, in the throwaway demo copy.
_BUG_FIXES = {
    "login": ("app/auth.py", 'os.environ["JWT_SECRET_KEY"]', 'os.environ["JWT_SECRET"]'),
    "orders-total": (
        "app/orders.py",
        "total = subtotal  # forgot to apply TAX_RATE here",
        "total = subtotal * (1 + TAX_RATE)",
    ),
    "orders-404": (
        "app/orders.py",
        "    order = ORDERS[order_id]",
        "    try:\n        order = ORDERS[order_id]\n    except KeyError:\n        raise OrderNotFoundError(order_id)",
    ),
}


def prepare_demo_project(incident_key: str) -> Path:
    """Copy sample_project to a temp dir and pre-fix every bug except this incident's."""
    demo_root = Path(tempfile.mkdtemp(prefix="agentforge_demo_project_"))
    shutil.copytree(
        PROJECT_ROOT / "sample_project",
        demo_root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"),
    )
    for key, (relative_path, old, new) in _BUG_FIXES.items():
        if key == incident_key:
            continue
        path = demo_root / relative_path
        content = path.read_text(encoding="utf-8")
        assert old in content, f"expected bug text for {key} not found - sample_project changed?"
        path.write_text(content.replace(old, new), encoding="utf-8")
    return demo_root


def print_section(title: str) -> None:
    print(f"\n{'=' * 8} {title} {'=' * 8}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentForge end-to-end demo")
    parser.add_argument("--incident", choices=INCIDENTS, default="login")
    args = parser.parse_args()

    try:
        client = GeminiClient()
    except GeminiConfigError as exc:
        print(f"Can't run the demo: {exc}")
        return

    title, description = INCIDENTS[args.incident]
    demo_project = prepare_demo_project(args.incident)
    workspace = create_incident_workspace(demo_project)

    print_section("Setup")
    print(f"Incident: {title}\n  {description}")
    print(f"Demo project (throwaway copy; other two bugs pre-fixed): {demo_project}")
    print(f"Sandbox workspace the agents will patch:                 {workspace}")
    print(f"Your real sample_project/ is never touched by this demo.")
    print(f"Tests in demo project BEFORE: {run_tests(demo_project).stdout.strip().splitlines()[-1]}")

    try:
        print_section("Ingesting knowledge base (Gemini embeddings)")
        collection = ingest_knowledge_base(PROJECT_ROOT / "knowledge_base", client)
        print(f"Stored {collection.count()} chunks.")

        graph = build_graph(client, collection, demo_project, workspace)
        initial = IncidentState(incident=Incident(title=title, description=description))

        print_section("Running the multi-agent workflow")
        merged: dict = {}
        for update in graph.stream(initial, stream_mode="updates"):
            for node_name, node_update in update.items():
                merged.update(node_update)
                latest = node_update.get("messages", [""])[-1]
                print(f"[{node_name}] {latest}")
        state = initial.model_copy(update=merged)
    except (GeminiRequestError, Exception) as exc:  # noqa: BLE001 - demo script: report and stop cleanly
        print(f"\nThe workflow stopped because of an error: {exc}")
        print("Nothing was applied to any real project.")
        return

    print_section("Result")
    print(f"Status:       {state.incident.status.value}")
    print(f"Retries used: {state.retry_count}")
    if state.root_cause:
        print(f"Root cause:   {state.root_cause.root_cause} (confidence {state.root_cause.confidence:.2f})")
        for item in state.root_cause.supporting_evidence:
            print(f"  evidence:   {item}")
    if state.patch_proposal:
        print(f"Patch target: {state.patch_proposal.target_file}\n  why: {state.patch_proposal.explanation}")
    if state.test_result:
        print(f"Sandbox tests: {state.test_result.summary}")
    if state.review_result:
        print(f"Review:       approved={state.review_result.approved}, risk={state.review_result.risk_level}")

    if state.incident.status != IncidentStatus.AWAITING_APPROVAL:
        print("\nNo fix reached the approval step, so nothing was applied.")
        return

    print_section("Human approval")
    if not sys.stdin.isatty():
        print("No interactive terminal - not applying anything.")
        return
    answer = input("Apply this fix to the demo project? [y/N] ").strip().lower()
    final = apply_human_decision(state, demo_project, workspace, approved=(answer == "y"))
    print(f"Final status: {final.incident.status.value}")
    if final.incident.status == IncidentStatus.RESOLVED:
        print(f"Demo project tests AFTER: {run_tests(demo_project).stdout.strip().splitlines()[-1]}")


if __name__ == "__main__":
    main()

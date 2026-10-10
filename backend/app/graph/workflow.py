"""
The LangGraph workflow tying every agent together.

    START
      |
    supervisor       (marks incident IN_PROGRESS)
      |
    investigation    (logs + repo evidence; 1 Gemini call to summarize)
      |
    knowledge        (Phase 3 agentic RAG over knowledge_base/)
      |
    debugging        (1 Gemini call -> RootCauseAnalysis)
      |
    coding  <-----.  (1 Gemini call -> PatchProposal; applied to SANDBOX only)
      |           |
    testing       |  (real pytest run in the sandbox, no LLM)
      |           |
    review -------+  (1 Gemini call -> ReviewResult)
      | route_after_review
      |-- approved and tests passed --> awaiting_approval --> END
      |-- otherwise, retries left   --> back to coding
      '-- otherwise, retries used   --> failed --> END

Every Gemini call goes through the one GeminiClient from Phase 1; every
filesystem/test action goes through the Phase 2 tools, scoped to the
sandbox workspace.
"""

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from app.agents import coding, debugging, human_approval, investigation, knowledge, review, supervisor, testing
from app.llm.gemini import GeminiClient
from app.models.incident_state import IncidentState

# Retries AFTER the first attempt, so the Coding Agent runs at most
# MAX_RETRIES + 1 times. The loop can never run forever.
MAX_RETRIES = 2


def route_after_review(state: IncidentState) -> str:
    """
    Decide what happens after Review. Only READS state and returns a
    routing key; retry_count is incremented inside the coding node.
    """
    if state.review_result and state.review_result.approved and state.test_result and state.test_result.all_passed:
        return "approve"
    if state.retry_count < MAX_RETRIES:
        return "retry"
    return "fail"


def build_graph(
    gemini_client: GeminiClient,
    knowledge_base_collection,
    sample_project_root: Path,
    workspace_root: Path,
    knowledge_base_root: Path | None = None,
    rag_mode: str = "vector",
):
    """
    Build and compile the graph. `workspace_root` must already be a
    sandbox copy of sample_project_root (see
    workspace.create_incident_workspace) - creating it outside keeps this
    function a pure "wire the nodes together" step.

    `knowledge_base_root` and `rag_mode` control the Knowledge Agent's
    retrieval strategy (see app/agents/knowledge.py) - both optional and
    backward compatible: omitting knowledge_base_root keeps the original
    Phase 4 behavior (vector retrieval, no keyword fallback available).
    """
    graph = StateGraph(IncidentState)

    graph.add_node("supervisor", supervisor.start_investigation)
    graph.add_node("investigation", investigation.build_investigation_node(gemini_client, workspace_root))
    graph.add_node(
        "knowledge",
        knowledge.build_knowledge_node(gemini_client, knowledge_base_collection, knowledge_base_root, rag_mode),
    )
    graph.add_node("debugging", debugging.build_debugging_node(gemini_client))
    graph.add_node("coding", coding.build_coding_node(gemini_client, workspace_root))
    graph.add_node("testing", testing.build_testing_node(workspace_root))
    graph.add_node("review", review.build_review_node(gemini_client, sample_project_root, workspace_root))
    graph.add_node("awaiting_approval", human_approval.mark_awaiting_approval)
    graph.add_node("failed", human_approval.mark_failed)

    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", "investigation")
    graph.add_edge("investigation", "knowledge")
    graph.add_edge("knowledge", "debugging")
    graph.add_edge("debugging", "coding")
    graph.add_edge("coding", "testing")
    graph.add_edge("testing", "review")
    graph.add_conditional_edges(
        "review", route_after_review, {"approve": "awaiting_approval", "retry": "coding", "fail": "failed"}
    )
    graph.add_edge("awaiting_approval", END)
    graph.add_edge("failed", END)

    return graph.compile()

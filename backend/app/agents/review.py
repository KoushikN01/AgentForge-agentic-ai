"""
Review/Security Agent.

The last automated check before a fix is eligible for human approval.
Reviews the ACTUAL diff (not just the Coding Agent's stated explanation)
alongside the real test results, and can reject a technically-passing fix
for being risky, out of scope, or not matching the diagnosed root cause.
"""

from pathlib import Path

from app.agents.workspace import compute_diff
from app.llm.gemini import GeminiClient
from app.models.agent_outputs import ReviewResult
from app.models.incident_state import IncidentState


def build_review_node(gemini_client: GeminiClient, sample_project_root: Path, workspace_root: Path):
    def review_patch(state: IncidentState) -> dict:
        if state.patch_proposal is None:
            # Coding always runs before review, but fail safe rather than crash.
            result = ReviewResult(
                approved=False, risk_level="high", concerns=["No patch was proposed"], reasoning="Nothing to review."
            )
            return {"review_result": result, "messages": state.messages + ["Review: no patch to review"]}

        diff = compute_diff(sample_project_root, workspace_root, state.patch_proposal.target_file)
        test_summary = state.test_result.summary if state.test_result else "(no test results)"

        prompt = (
            f"Incident: {state.incident.title}\n{state.incident.description}\n\n"
            f"Root cause: {state.root_cause.root_cause if state.root_cause else '(unknown)'}\n\n"
            f"Proposed fix explanation: {state.patch_proposal.explanation}\n\n"
            f"Actual diff:\n{diff}\n\n"
            f"Test results: {test_summary}"
        )
        review = gemini_client.generate_structured(
            prompt,
            response_model=ReviewResult,
            system_instruction=(
                "You are the Review/Security Agent in a software incident investigation "
                "system. Approve only if the diff is scoped to the root cause, the tests "
                "passed, and the change introduces no obvious security or safety risk. "
                "A change that passes tests but doesn't match the diagnosed root cause, or "
                "touches more than necessary, should not be approved."
            ),
        )
        return {
            "review_result": review,
            "messages": state.messages + [f"Review: approved={review.approved}, risk={review.risk_level}"],
        }

    return review_patch

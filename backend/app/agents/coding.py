"""
Coding Agent.

Proposes a fix as a PatchProposal (find-and-replace on one file), then
applies it with workspace.apply_patch(), which only ever touches the
sandbox copy - never the real project. If applying fails (the proposed
snippet doesn't match the file), we log it and let the Test Agent's next
run fail naturally instead of crashing the graph; the retry loop already
handles "still broken".

On a retry (this node running again after a failed test/review), the
previous attempt's feedback is folded into the prompt. This is the
project's "reflection" requirement: the Coding Agent sees WHY its last
attempt failed instead of blindly repeating it.
"""

import re
from pathlib import Path

from app.agents.workspace import PatchApplyError, apply_patch
from app.llm.gemini import GeminiClient
from app.models.agent_outputs import PatchProposal
from app.models.incident_state import IncidentState
from app.tools import repo_tools

# Pulls "path/to/file.py" out of evidence lines like "app/auth.py:42: code".
_FILE_PATH_PATTERN = re.compile(r"^([\w./_-]+\.py):\d+:")
_MAX_FILES_TO_SHOW = 3


def _relevant_file_contents(workspace_root: Path, evidence: list[str]) -> str:
    paths: list[str] = []
    for line in evidence:
        match = _FILE_PATH_PATTERN.match(line)
        if match and match.group(1) not in paths:
            paths.append(match.group(1))

    sections = []
    for path in paths[:_MAX_FILES_TO_SHOW]:
        try:
            sections.append(f"--- {path} ---\n{repo_tools.read_file(workspace_root, path)}")
        except FileNotFoundError:
            continue
    return "\n\n".join(sections)


def build_coding_node(gemini_client: GeminiClient, workspace_root: Path):
    def propose_and_apply_patch(state: IncidentState) -> dict:
        # A test_result already on the state means a previous attempt ran.
        is_retry = state.test_result is not None
        retry_count = state.retry_count + 1 if is_retry else state.retry_count

        feedback = None
        if is_retry:
            parts = []
            if state.test_result and not state.test_result.all_passed:
                parts.append(f"Tests after the previous attempt: {state.test_result.summary}")
            if state.review_result and not state.review_result.approved:
                concerns = "; ".join(state.review_result.concerns) or state.review_result.reasoning
                parts.append(f"Review concerns: {concerns}")
            feedback = " | ".join(parts) or "The previous attempt did not pass."

        root_cause_text = state.root_cause.root_cause if state.root_cause else "(unknown)"
        prompt = (
            f"Incident: {state.incident.title}\n{state.incident.description}\n\n"
            f"Root cause: {root_cause_text}\n\n"
            f"Relevant source files:\n{_relevant_file_contents(workspace_root, state.evidence)}\n"
        )
        if feedback:
            prompt += f"\nA previous fix attempt did not work: {feedback}\nPropose a different fix.\n"

        patch = gemini_client.generate_structured(
            prompt,
            response_model=PatchProposal,
            system_instruction=(
                "You are the Coding Agent in a software incident investigation system. "
                "Propose the smallest fix that addresses the root cause. original_snippet "
                "must be copied EXACTLY from the shown file content, including whitespace, "
                "so it can be found and replaced automatically."
            ),
        )

        messages = list(state.messages)
        try:
            apply_patch(workspace_root, patch)
            messages.append(f"Coding: applied patch to {patch.target_file} in the sandbox workspace")
        except PatchApplyError as exc:
            messages.append(f"Coding: could not apply proposed patch to {patch.target_file}: {exc}")

        return {
            "patch_proposal": patch,
            "retry_count": retry_count,
            "retry_feedback": feedback,
            "messages": messages,
        }

    return propose_and_apply_patch

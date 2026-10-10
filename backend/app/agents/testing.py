"""
Test Agent.

Runs the sandbox workspace's own test suite with Phase 2's
test_tools.run_tests() - plain deterministic execution, no LLM. A patch's
explanation is never treated as evidence it works; the real test results
are.
"""

from pathlib import Path

from app.models.agent_outputs import TestOutcome
from app.models.incident_state import IncidentState
from app.tools import test_tools


def build_testing_node(workspace_root: Path):
    def run_tests_node(state: IncidentState) -> dict:
        result = test_tools.run_tests(workspace_root)
        outcome = TestOutcome(
            passed=result.passed,
            failed=result.failed,
            all_passed=result.all_passed,
            summary=f"{result.passed} passed, {result.failed} failed",
        )
        return {
            "test_result": outcome,
            "messages": state.messages + [f"Testing: {outcome.summary}"],
        }

    return run_tests_node

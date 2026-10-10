"""
Structured output schemas for the Phase 4 agents.

Each of these is a Pydantic model an agent asks Gemini to return via
GeminiClient.generate_structured() (see app/llm/gemini.py). Living in
app/models/ (not app/agents/) keeps the layering one-directional:
app/agents/ depends on app/models/, never the other way around.
"""

from pydantic import BaseModel, Field


class EvidenceSummary(BaseModel):
    """The Investigation Agent's read on the raw logs/code evidence it gathered."""

    summary: str = Field(description="A few sentences summarizing what the evidence shows")
    key_findings: list[str] = Field(description="Short bullet-point findings, most important first")


class RootCauseAnalysis(BaseModel):
    """The Debugging Agent's diagnosis."""

    root_cause: str = Field(description="The most likely root cause, in one or two sentences")
    confidence: float = Field(description="0.0 to 1.0 confidence in this diagnosis")
    supporting_evidence: list[str] = Field(
        description="Which specific pieces of evidence support this diagnosis"
    )


class PatchProposal(BaseModel):
    """
    The Coding Agent's proposed fix.

    Deliberately simple (find-and-replace on one file) rather than a full
    unified diff: easy to read, easy to apply safely to a sandbox copy, and
    easy to validate (original_snippet must match the file exactly once, or
    the patch is rejected - see app/agents/workspace.py).
    """

    target_file: str = Field(description="Path to the file to change, relative to the project root")
    explanation: str = Field(description="Why this change fixes the root cause")
    original_snippet: str = Field(description="The exact existing code to find and replace")
    replacement_snippet: str = Field(description="The code to replace it with")
    relevant_test_path: str = Field(
        description="Path to the test file that verifies this fix, e.g. 'tests/test_auth.py'"
    )


class TestOutcome(BaseModel):
    """A compact summary of a test run, small enough to keep in IncidentState."""

    __test__ = False  # tell pytest this isn't a test class, despite the name

    passed: int
    failed: int
    all_passed: bool
    summary: str  # e.g. "3 passed, 1 failed"


class ReviewResult(BaseModel):
    """The Review/Security Agent's verdict on a proposed, tested patch."""

    approved: bool
    risk_level: str = Field(description="One of: low, medium, high")
    concerns: list[str] = Field(default_factory=list, description="Specific concerns, if any")
    reasoning: str

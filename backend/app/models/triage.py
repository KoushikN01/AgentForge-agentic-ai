"""
IncidentTriage: a tiny structured-output example.

This isn't a full agent (that comes in a later phase) — it exists so
Phase 1 can demonstrate and test `GeminiClient.generate_structured()` with
a schema that's actually relevant to AgentForge's domain, instead of a
throwaway example unrelated to the project.

In a later phase, the Supervisor Agent will use something like this to
decide an incident's severity before starting an investigation.
"""

from pydantic import BaseModel, Field


class IncidentTriage(BaseModel):
    """Gemini's first-pass read on how serious an incident report is."""

    severity: str = Field(description="One of: low, medium, high, critical")
    reasoning: str = Field(description="One or two sentences explaining the severity")

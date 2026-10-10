"""
Investigation Agent.

Gathers evidence with the Phase 2 tools (log_tools, repo_tools) - plain
deterministic Python - then makes ONE Gemini call to summarize what was
found. Reading and filtering logs doesn't need an LLM; making sense of
them does.

    logs/app.log --filter ERROR--> error entries
                                        | extract exception names / quoted tokens
                                   repo_tools.search_repository
                                        |
                              raw evidence (logs + code matches)
                                        | ONE Gemini call
                              EvidenceSummary (key_findings)
"""

import re
from pathlib import Path

from app.llm.gemini import GeminiClient
from app.models.agent_outputs import EvidenceSummary
from app.models.incident_state import IncidentState
from app.tools import log_tools, repo_tools

# Heuristic search terms from a log message: Python exception class names
# (KeyError) and quoted identifiers ('JWT_SECRET_KEY'). Meant to find a few
# promising leads in the code, not to be a complete log parser.
_EXCEPTION_PATTERN = re.compile(r"\b[A-Z][A-Za-z]*Error\b")
_QUOTED_PATTERN = re.compile(r"'([^']+)'")
_MAX_SEARCH_TERMS = 3


def _extract_search_terms(message: str) -> list[str]:
    terms: list[str] = []
    for term in _EXCEPTION_PATTERN.findall(message) + _QUOTED_PATTERN.findall(message):
        if term not in terms:
            terms.append(term)
    return terms


def build_investigation_node(gemini_client: GeminiClient, workspace_root: Path):
    def investigate(state: IncidentState) -> dict:
        log_entries = log_tools.read_log_entries(workspace_root, "logs/app.log")
        error_entries = log_tools.filter_by_level(log_entries, "ERROR")

        evidence = [
            f"logs/app.log [{e.timestamp}] {e.level} request_id={e.request_id}: {e.message}"
            for e in error_entries
        ]

        search_terms: list[str] = []
        for entry in error_entries:
            for term in _extract_search_terms(entry.message):
                if term not in search_terms:
                    search_terms.append(term)
        for term in search_terms[:_MAX_SEARCH_TERMS]:
            for match in repo_tools.search_repository(workspace_root, term):
                evidence.append(f"{match.path}:{match.line_number}: {match.line}")

        prompt = (
            f"Incident: {state.incident.title}\n{state.incident.description}\n\n"
            "Raw evidence gathered from logs and source code:\n" + "\n".join(f"- {e}" for e in evidence)
        )
        summary = gemini_client.generate_structured(
            prompt,
            response_model=EvidenceSummary,
            system_instruction=(
                "You are the Investigation Agent in a software incident investigation "
                "system. Summarize the raw evidence into a few clear key findings. "
                "You don't diagnose the root cause yet - that's the Debugging Agent's job."
            ),
        )

        return {
            "evidence": evidence,
            "messages": state.messages
            + [f"Investigation: {summary.summary}"]
            + [f"finding: {f}" for f in summary.key_findings],
        }

    return investigate

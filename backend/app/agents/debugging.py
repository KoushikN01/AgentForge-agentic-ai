"""
Debugging Agent.

Takes the Investigation Agent's evidence and the Knowledge/RAG Agent's
context and asks Gemini for one structured diagnosis: the root cause, a
confidence, and the specific evidence supporting it. This makes the
"evidence vs. inference" requirement concrete - RootCauseAnalysis always
carries its supporting_evidence alongside the conclusion.
"""

from app.llm.gemini import GeminiClient
from app.models.agent_outputs import RootCauseAnalysis
from app.models.incident_state import IncidentState


def build_debugging_node(gemini_client: GeminiClient):
    def analyze_root_cause(state: IncidentState) -> dict:
        prompt = (
            f"Incident: {state.incident.title}\n{state.incident.description}\n\n"
            "Evidence gathered:\n" + "\n".join(f"- {e}" for e in state.evidence) + "\n\n"
            "Relevant knowledge base context:\n" + "\n".join(f"- {c}" for c in state.knowledge_context)
        )
        analysis = gemini_client.generate_structured(
            prompt,
            response_model=RootCauseAnalysis,
            system_instruction=(
                "You are the Debugging Agent in a software incident investigation system. "
                "Diagnose the single most likely root cause from the evidence and knowledge "
                "base context given. Cite which specific evidence supports your diagnosis - "
                "never state a root cause without grounding it in the evidence provided."
            ),
        )
        return {
            "root_cause": analysis,
            "messages": state.messages
            + [f"Debugging: root cause = {analysis.root_cause} (confidence {analysis.confidence:.2f})"],
        }

    return analyze_root_cause

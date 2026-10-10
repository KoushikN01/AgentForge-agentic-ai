"""
Agentic RAG.

Traditional RAG (retrieval.semantic_search): the incident text itself is
used as the search query, once.

Agentic RAG (this module): an LLM call first decides *what* to search for
(which may differ from the incident text verbatim — e.g. an incident
about "login failing" should also search for "environment variable
configuration"), the retrieved chunks get evaluated for whether they
actually explain the incident, and if not, another round of retrieval
runs with a refined plan — up to MAX_ROUNDS times so this can never loop
forever.

    Incident
      ↓
    decide_what_to_search (Gemini, structured output) -> RetrievalPlan
      ↓
    run each query through retrieval.semantic_search
      ↓
    check_sufficiency (Gemini, structured output) -> SufficiencyCheck
      ↓
    sufficient? -> done : another round (up to MAX_ROUNDS)
"""

from app.llm.gemini import GeminiClient
from app.rag.models import (
    AgenticRetrievalResult,
    RetrievalPlan,
    RetrievalRound,
    RetrievedChunk,
    SufficiencyCheck,
)
from app.rag.retrieval import semantic_search

MAX_ROUNDS = 2


def decide_what_to_search(
    gemini_client: GeminiClient, incident_description: str, previous_feedback: str | None = None
) -> RetrievalPlan:
    """Ask Gemini what to search the knowledge base for, given the incident."""
    prompt = (
        "An incident was reported. Decide what to search a software "
        "engineering knowledge base for in order to investigate it. "
        "Propose 1-3 short, specific search queries.\n\n"
        f"Incident:\n{incident_description}"
    )
    if previous_feedback:
        prompt += f"\n\nA previous search round was insufficient because: {previous_feedback}"

    return gemini_client.generate_structured(
        prompt,
        response_model=RetrievalPlan,
        system_instruction=(
            "You are the Knowledge/RAG agent in a software incident investigation "
            "system. You don't answer the incident yourself — you only decide what "
            "to search for."
        ),
    )


def check_sufficiency(
    gemini_client: GeminiClient, incident_description: str, retrieved: list[RetrievedChunk]
) -> SufficiencyCheck:
    """Ask Gemini whether the retrieved chunks are enough to explain the incident."""
    context = "\n\n---\n\n".join(
        f"[{r.chunk.source_path}]\n{r.chunk.text}" for r in retrieved
    )
    prompt = (
        f"Incident:\n{incident_description}\n\n"
        f"Retrieved knowledge base excerpts:\n{context}\n\n"
        "Do these excerpts contain enough information to explain the likely "
        "cause of this incident? If not, say what's missing."
    )
    return gemini_client.generate_structured(
        prompt,
        response_model=SufficiencyCheck,
        system_instruction=(
            "You are the Knowledge/RAG agent in a software incident investigation "
            "system, deciding whether enough evidence has been retrieved."
        ),
    )


def agentic_retrieve(
    gemini_client: GeminiClient, collection, incident_description: str, k_per_query: int = 2
) -> AgenticRetrievalResult:
    """Run the full agentic retrieval loop for one incident."""
    rounds: list[RetrievalRound] = []
    feedback: str | None = None
    all_retrieved: list[RetrievedChunk] = []

    for round_number in range(1, MAX_ROUNDS + 1):
        plan = decide_what_to_search(gemini_client, incident_description, previous_feedback=feedback)

        round_chunks: list[RetrievedChunk] = []
        seen_ids: set[str] = {r.chunk.id for r in all_retrieved}
        for query in plan.queries:
            for result in semantic_search(collection, gemini_client, query, k=k_per_query):
                if result.chunk.id not in seen_ids:
                    round_chunks.append(result)
                    seen_ids.add(result.chunk.id)

        all_retrieved.extend(round_chunks)
        sufficiency = check_sufficiency(gemini_client, incident_description, all_retrieved)

        rounds.append(
            RetrievalRound(round_number=round_number, plan=plan, retrieved=round_chunks, sufficiency=sufficiency)
        )

        if sufficiency.is_sufficient:
            break
        feedback = sufficiency.missing_information

    return AgenticRetrievalResult(rounds=rounds, final_chunks=all_retrieved)

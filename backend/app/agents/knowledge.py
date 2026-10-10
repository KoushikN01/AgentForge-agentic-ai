"""
Knowledge/RAG Agent.

Wraps Phase 3's retrieval so the Debugging Agent gets grounded
documentation context. Two retrieval strategies, controlled by
Settings.rag_mode (env var RAG_MODE):

- "vector" (default): agentic_retrieve() - Gemini decides what to search
  for, retrieves, judges sufficiency, retries if needed (see
  app/rag/agentic_retrieval.py). If that fails for any reason (no API
  key, a quota error, a network error - anything GeminiRequestError
  covers), this node FALLS BACK to free keyword search
  (app/tools/doc_tools.search_docs) rather than returning no knowledge
  context at all. The fallback is recorded in the returned messages, not
  hidden.
- "keyword": always use doc_tools.search_docs directly - zero Gemini
  calls, zero cost, works with no API key at all.

Either way the Debugging Agent sees the same shape of data
(knowledge_context: list[str]) - it doesn't know or care which strategy
produced it.
"""

from pathlib import Path

from app.llm.gemini import GeminiClient, GeminiRequestError
from app.models.incident_state import IncidentState
from app.rag.agentic_retrieval import agentic_retrieve
from app.tools import doc_tools


def _keyword_context(knowledge_base_root: Path, state: IncidentState) -> list[str]:
    """
    doc_tools.search_docs matches a whole phrase verbatim (Phase 2's
    deliberately simple keyword search - see its own docstring), so
    searching the full title+description almost never hits anything real.
    Instead, try the title, then the description, then each individual
    word from the title longer than 3 characters - accumulating every
    distinct document any of those terms matches. Still zero-cost, still
    fully deterministic; just gives this fallback a real chance to find
    something, the way a person searching documentation by hand would try
    a few different phrasings rather than one long sentence.
    """
    candidates = [state.incident.title, state.incident.description] + [
        word.strip(".,!?'\"") for word in state.incident.title.split() if len(word) > 3
    ]
    seen_paths: set[str] = set()
    context: list[str] = []
    for query in candidates:
        for match in doc_tools.search_docs(knowledge_base_root, query):
            if match.path not in seen_paths:
                seen_paths.add(match.path)
                context.append(f"{match.path}: {match.snippet}")
    return context


def build_knowledge_node(
    gemini_client: GeminiClient,
    knowledge_base_collection,
    knowledge_base_root: Path | None = None,
    rag_mode: str = "vector",
):
    def retrieve_knowledge(state: IncidentState) -> dict:
        if rag_mode == "keyword":
            if knowledge_base_root is None:
                raise ValueError("rag_mode='keyword' requires knowledge_base_root to be set.")
            context = _keyword_context(knowledge_base_root, state)
            return {
                "knowledge_context": context,
                "messages": state.messages + [f"Knowledge retrieval (keyword mode): {len(context)} excerpt(s) found"],
            }

        description = f"{state.incident.title}\n{state.incident.description}"
        try:
            result = agentic_retrieve(gemini_client, knowledge_base_collection, description)
        except GeminiRequestError as exc:
            if knowledge_base_root is None:
                raise  # no fallback available - propagate like before
            context = _keyword_context(knowledge_base_root, state)
            return {
                "knowledge_context": context,
                "messages": state.messages
                + [
                    f"Knowledge retrieval: vector search failed ({exc}); "
                    f"fell back to keyword search, found {len(context)} excerpt(s)"
                ],
            }

        context = [f"{c.chunk.source_path}: {c.chunk.text}" for c in result.final_chunks]
        return {
            "knowledge_context": context,
            "messages": state.messages
            + [
                f"Knowledge retrieval: {len(context)} excerpt(s) found in "
                f"{len(result.rounds)} round(s), sufficient={result.stopped_because_sufficient}"
            ],
        }

    return retrieve_knowledge

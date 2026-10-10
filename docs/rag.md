# RAG: traditional, agentic, and the keyword fallback

## The pipeline

```
knowledge_base/*.md
    | doc_tools.list_documents / get_document   (app/tools/doc_tools.py)
raw document text
    | chunking.chunk_text                        (app/rag/chunking.py)
list[Chunk]  (paragraph-aware, ~600 chars, no LLM)
    | GeminiClient.embed_texts(task_type=RETRIEVAL_DOCUMENT)   (app/llm/gemini.py)
list[list[float]]  (model: gemini-embedding-001, 768 dimensions)
    | vector_store.add_chunks                     (app/rag/vector_store.py)
Chroma collection (in-memory, rebuilt at startup - app/main.py)
```

## Traditional vs. agentic retrieval

**Traditional** (`app/rag/retrieval.py`'s `semantic_search`): embed the
query once, return the k nearest chunks. `Question -> Retrieve -> Answer`.

**Agentic** (`app/rag/agentic_retrieval.py`'s `agentic_retrieve`, what the
Knowledge Agent actually uses by default): a Gemini call first decides
*what* to search for (`RetrievalPlan` - may differ from the incident text
verbatim), the retrieved chunks get evaluated for sufficiency
(`SufficiencyCheck`), and if insufficient, another round runs with the
gap fed back into the next search - up to `MAX_ROUNDS = 2`, so it can
never loop forever.

## The keyword fallback - and how to control it

`RAG_MODE` (env var, default `vector`):

- `vector` - agentic retrieval as above. If the Gemini call fails for any
  reason (`GeminiRequestError` - no key, quota, network), the Knowledge
  Agent (`app/agents/knowledge.py`) catches it and falls back to free
  keyword search instead of returning no context at all - and says so in
  the incident's message log, not silently.
- `keyword` - skip embeddings entirely, always use
  `doc_tools.search_docs` (plain substring matching, zero Gemini calls,
  zero cost, works with no API key at all).

Either mode produces the same shape of data
(`knowledge_context: list[str]`) - the Debugging Agent downstream doesn't
know or care which one produced it. This is not a pretend fallback: both
modes are real, both are tested (`backend/tests/test_agent_knowledge.py`),
and the choice is one environment variable, documented in `.env.example`.

## What's NOT verified

No real Gemini embedding call has been made in the environment this
project was built in (no API key, no network path to Google's API - see
root `BUILD_VERIFICATION.md`). Chunking, the vector store, and the
agentic-retrieval control loop are all tested for real with hand-made or
scripted vectors; actual embedding *quality* against this knowledge base
is unverified. Run `python scripts/rag_demo.py` with a real key to check.

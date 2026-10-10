# Interview guide

Honest answers about what this project actually does, grounded in real
files you can open. No invented metrics, no claims this project doesn't
back up.

## 30 seconds

"AgentForge is a multi-agent system, built with LangGraph and Gemini,
that investigates software incidents end to end: it reads logs and code,
retrieves relevant documentation with RAG, diagnoses a root cause,
proposes and tests a fix in an isolated sandbox, runs a safety review,
and only applies the fix to the real project after a human approves it.
It's exposed through a FastAPI backend with persistence, and a React
frontend to drive the whole flow."

## 2 minutes

Add: there's a seven-agent LangGraph workflow (Supervisor, Investigation,
Knowledge/RAG, Debugging, Coding, Testing, Review), each using Gemini
only where reasoning is actually needed - reading files and running tests
are plain deterministic Python, not LLM calls, which keeps it fast and
cheap. The Coding Agent's patch is validated and applied to a throwaway
copy of the target project, never the real one; a Review Agent checks the
actual diff and real test results before anything can reach a human for
approval; and a bounded retry loop (reflection: the next attempt sees
*why* the last one failed) gives the system a chance to self-correct
before giving up. Everything - the graph routing, the sandbox safety, the
retry loop, the API - is covered by real tests, most using a scripted
Gemini client so the suite runs without an API key or real cost.

## 5 minutes: architecture

Walk through `docs/architecture.md`'s diagram: frontend -> FastAPI ->
SQLite (IncidentState persisted as JSON) -> LangGraph -> the seven agents
-> the sandbox -> human approval -> the real project. Mention the RAG
pipeline separately (`docs/rag.md`): chunking -> Gemini embeddings ->
Chroma -> agentic retrieval, with a free keyword-search fallback
controlled by one environment variable if embeddings aren't available.

## Why multiple agents, not one?

Separation of concerns made concrete: Investigation only gathers evidence,
Debugging only diagnoses, Coding only proposes/applies - each step has a
narrow job and a typed, validated output (Pydantic structured outputs),
rather than one prompt trying to reason about everything and hoping the
free-text response can be parsed reliably. It also makes retries
meaningful: a failed attempt can retry *just* coding with feedback,
instead of re-running the whole investigation from scratch.

## Why LangGraph specifically?

The one genuinely non-linear part of this workflow - approve / retry /
fail after Review - is a real graph routing decision. LangGraph makes
that an explicit, testable function (`route_after_review`) operating on a
typed state object, instead of if/else branches buried in a loop.

## Why Gemini?

Free-tier API access for a learning project, and the `google-genai` SDK's
structured-output support (`response_schema`) maps directly onto Pydantic
models - no manual JSON-parsing-and-hoping.

## Why human-in-the-loop?

The system can be wrong - the retry loop improves the odds, but doesn't
guarantee a correct fix. `apply_human_decision()` is the single
chokepoint for every path that could change the real project, and it's
explicitly not automatic.

## How are tools secured?

An allowlist, not a sandbox-everything approach: deterministic tools
only ever run specific, safe operations (read a file inside a resolved
root, run `pytest` on a path inside the project, `git diff`/`status`) -
never an arbitrary shell string. See `docs/security.md` for the full
table.

## How is the system evaluated?

`evaluation/run_evaluation.py` runs the full graph against every real bug
`sample_project` actually has (three - not an inflated number) and
measures whether the proposed patch targeted the right file, whether the
sandbox tests passed, and how many retries it took. See `docs/rag.md`
and the project's `BUILD_VERIFICATION.md` for exactly what was measured
with a scripted vs. a real Gemini client.

## What happens when an agent fails?

An exception during the graph run is caught in
`backend/app/api/routes.py`'s `_run_investigation`, recorded as a
`FAILED` incident with the real error message (not hidden), and the
sandbox is cleaned up since nothing will read it again.

## How do retries work?

Capped at `MAX_RETRIES = 2` (3 attempts total). The router only reads
state; the Coding Agent itself increments the counter and builds the
feedback prompt for the next attempt.

## How would you scale it?

Swap SQLite for Postgres (`DATABASE_URL`, no code change), move the
background task to a real queue if investigations need to survive a
process restart mid-run, persist the vector store instead of re-ingesting
at startup, and add auth/rate-limiting to the API - all explicitly listed
as not-yet-done in `docs/security.md` and the root `BUILD_VERIFICATION.md`,
not silently missing.

## What would you improve?

Multi-file patches (today: one find-and-replace per attempt), retries
returning to Debugging when the root cause itself might be wrong (today:
always retries Coding), and real embedding-quality evaluation against
live Gemini (only scripted-Gemini evaluation has actually been run in the
environment this was built in).

## What are the limitations?

Static Supervisor routing (not an LLM choosing the next agent - the
workflow is linear enough not to need it), no API authentication, no
Docker daemon available to runtime-verify the Docker setup, and - stated
plainly rather than glossed over - no live-Gemini run has been performed
in this build environment; every automated test uses a scripted client.

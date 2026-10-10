<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/LangGraph-Multi_Agent-FF6F00?style=for-the-badge&logo=chainlink&logoColor=white" />
  <img src="https://img.shields.io/badge/Google_Gemini-LLM-4285F4?style=for-the-badge&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/React-Frontend-61DAFB?style=for-the-badge&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/ChromaDB-Vector_Store-FF6F61?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
</p>

# AgentForge

A multi-agent AI system that investigates software incidents the way a real engineer would. It reads logs, searches the codebase, pulls relevant documentation through RAG, figures out what went wrong, writes a fix, runs actual tests against it, reviews the diff for safety, and then stops and waits for a human to approve before touching anything real.

Built with **LangGraph**, **Agentic RAG (ChromaDB + Gemini embeddings)**, **FastAPI**, and **React**. Not a chatbot with a UI slapped on top. There are 7 agents, 131 tests, and a real evaluation harness.

---

## What problem does this solve?

Say someone files a bug: *"The login endpoint is returning 500 errors."*

Normally a developer would go check the logs, grep through the code, look at the docs, form a hypothesis, try a fix, run the tests, review it. That's exactly what AgentForge does, except each step is handled by a dedicated AI agent:

```
Bug report comes in
       |
Investigation Agent    reads logs and greps the source code
       |
Knowledge Agent        searches docs/runbooks using Agentic RAG
       |
Debugging Agent        diagnoses the root cause based on evidence
       |
Coding Agent           writes a fix (only in a sandbox copy, never the real code)
       |
Testing Agent          runs real pytest, not "the AI thinks it looks fine"
       |
Review Agent           checks the actual diff for risks
       |
Human Approval         you look at everything and decide: apply or reject
```

The whole point is that agents pass structured data to each other through a shared state, and nothing touches your real codebase until you explicitly say so.

---

## Architecture overview

```
React Frontend (:5173)
    Dashboard, Incident Detail, Timeline
         |
         | REST API calls (JSON over HTTP)
         v
FastAPI Backend (:8000)
    Routes, Schemas, SQLAlchemy ORM, Background Tasks
         |
         v
LangGraph StateGraph (the multi-agent workflow)

    Supervisor --> Investigation --> Knowledge --> Debugging --> Coding --> Testing --> Review
                                                                  ^                      |
                                                                  |   route_after_review  |
                                                                  +------- retry ---------+
                                                  approved --> awaiting_approval --> END
                                                  retries used up --> failed --> END
         |
         v
Sandbox Workspace
    Every code change happens in a throwaway temp copy.
    Only apply_human_decision() can write to the real project.
```

---

## How the agents work

There are 7 agents in the pipeline. Some call Gemini, some don't. Here's what each one actually does:

**Supervisor** sets the incident status to `in_progress`. No LLM call. The workflow is linear enough that having an LLM decide "what's next" would just add cost and randomness for no benefit.

**Investigation Agent** reads `logs/app.log` and greps through the source files using the repo tools. Then one Gemini call summarizes all that raw evidence into key findings. Code: `backend/app/agents/investigation.py`

**Knowledge Agent (RAG)** retrieves relevant documentation from the knowledge base. This is where the Agentic RAG happens. More on that below. Code: `backend/app/agents/knowledge.py`

**Debugging Agent** takes the evidence from Investigation and the docs from Knowledge, and makes one Gemini call to produce a `RootCauseAnalysis` with a confidence score and the specific evidence backing it. Code: `backend/app/agents/debugging.py`

**Coding Agent** proposes a find-and-replace patch targeting one file. The fix is applied only to the sandbox workspace, never the real project. On retries, it gets feedback about what went wrong last time (test failures, review concerns) so it doesn't repeat the same mistake. Code: `backend/app/agents/coding.py`

**Testing Agent** runs the actual `pytest` suite inside the sandbox. No LLM. The test exit code is what matters, not an AI's opinion. Code: `backend/app/agents/testing.py`

**Review Agent** looks at the real `git diff` plus the test results and decides if the fix is safe. It can reject a fix that technically passes tests but seems risky or out of scope. Code: `backend/app/agents/review.py`

After Review, the graph routes based on the outcome: if approved and tests passed, it goes to `awaiting_approval`. If there are retries left, it loops back to Coding with the feedback. If retries are exhausted (`MAX_RETRIES = 2`), it marks the incident as failed. The loop physically cannot run forever.

---

## Agentic RAG (not just basic retrieval)

This is one of the core things I wanted to get right. Basic RAG just embeds the query and does a similarity search. That works, but it's limited. If someone reports "login is failing," you'd also want to search for "environment variable configuration" and "JWT setup." The incident text alone doesn't always contain the right search terms.

**How Agentic RAG works here:**

The Knowledge Agent asks Gemini to generate a `RetrievalPlan` with 1 to 3 targeted search queries based on the incident. Those queries are run against a ChromaDB vector store (embeddings via `gemini-embedding-001`, 768 dimensions). Then Gemini evaluates the retrieved chunks: are they actually sufficient to explain this incident? If not, it says what's missing, and another round of retrieval happens with refined queries. This runs up to 2 rounds max.

```
Incident description
       |
Gemini generates search queries (RetrievalPlan)
       |
Vector search in ChromaDB for each query
       |
Gemini checks: "Is this enough?" (SufficiencyCheck)
       |
   sufficient? --> done, pass context to Debugging Agent
   not enough? --> generate better queries, try again (max 2 rounds)
```

There's also a fallback. If the Gemini API call fails for any reason (no key, quota, network error), the system catches the exception and falls back to plain keyword search over the markdown files. Zero downtime, and it's logged so you can see exactly what happened. You can also force keyword mode by setting `RAG_MODE=keyword` in the environment.

Both modes produce the same data shape (`knowledge_context: list[str]`), so the Debugging Agent downstream doesn't know or care which strategy retrieved the docs.

The full RAG pipeline: `backend/app/rag/`
- `chunking.py` splits docs into ~600 char chunks (paragraph-aware, no LLM)
- `vector_store.py` manages the ChromaDB collection
- `ingest.py` handles the ingestion pipeline at startup
- `agentic_retrieval.py` is the iterative retrieval loop
- `retrieval.py` is the simpler baseline semantic search

---

## LangGraph workflow

The whole multi-agent pipeline is wired together as a LangGraph `StateGraph`. This is the actual code (simplified):

```python
graph = StateGraph(IncidentState)

graph.add_node("supervisor", supervisor.start_investigation)
graph.add_node("investigation", investigation.build_investigation_node(...))
graph.add_node("knowledge", knowledge.build_knowledge_node(...))
graph.add_node("debugging", debugging.build_debugging_node(...))
graph.add_node("coding", coding.build_coding_node(...))
graph.add_node("testing", testing.build_testing_node(...))
graph.add_node("review", review.build_review_node(...))

# This is the interesting part: conditional routing after review
graph.add_conditional_edges(
    "review",
    route_after_review,
    {"approve": "awaiting_approval", "retry": "coding", "fail": "failed"}
)
```

`IncidentState` is the shared Pydantic model that every agent reads from and writes to. It carries the incident details, evidence, root cause analysis, patch proposal, test results, review results, retry count, and messages.

Why LangGraph instead of just a for-loop? Because the retry/approve/fail branching after Review is a real graph routing decision. `route_after_review` is a pure function that reads the state and returns `"approve"`, `"retry"`, or `"fail"`. LangGraph makes that explicit and testable instead of burying it in nested if/else blocks.

Code: `backend/app/graph/workflow.py`

---

## Reflection and retry

When the Coding Agent runs again after a failed attempt, it doesn't just try again blindly. It gets the previous test results and review concerns folded into the prompt:

```python
if is_retry:
    feedback = f"Tests: {state.test_result.summary} | Review: {state.review_result.concerns}"
    prompt += f"\nPrevious fix failed: {feedback}\nPropose a DIFFERENT fix.\n"
```

The sandbox also keeps the earlier edits rather than resetting, so retries build on what's already there. This is a simple but real implementation of the reflection pattern.

---

## Safety model

The core assumption: the LLM is not malicious, but it is frequently wrong. The system needs to be safe even when the AI produces bad output.

**Sandbox isolation** Every patch the Coding Agent proposes gets applied to a throwaway temp-directory copy of `sample_project/`. The real project directory is never touched by any agent. (`backend/app/agents/workspace.py`)

**Path traversal guards** Every file operation goes through `security.py`'s `resolve_within_root()`, which blocks paths like `../../etc/passwd`. This applies to all the tools (log, repo, doc, test, git) and to the workspace itself.

**Patch validation** When applying a patch, the original snippet must match the file content exactly once. Zero matches means the patch is stale. Multiple matches means it's ambiguous. Either way, it's rejected outright, not applied on a best-effort basis.

**Real test execution** The Testing Agent runs `pytest` for real. It doesn't ask the LLM if the code looks correct.

**Bounded retries** `MAX_RETRIES = 2`, meaning the Coding Agent runs at most 3 times total. The loop cannot run indefinitely.

**Human approval gate** `apply_human_decision()` is the only function in the entire codebase that can copy a fixed file from the sandbox into the real project, and only when explicitly called with `approved=True`. The frontend's approve/reject buttons call the same API endpoint. There is no code path that bypasses this.

---

## Structured LLM outputs

Every Gemini call that produces data for downstream agents uses `generate_structured()` with a Pydantic model as the schema:

```python
class RootCauseAnalysis(BaseModel):
    root_cause: str
    confidence: float
    supporting_evidence: list[str]

class PatchProposal(BaseModel):
    target_file: str
    original_snippet: str
    replacement_snippet: str
    explanation: str
```

Gemini returns JSON matching the schema, Pydantic validates it. If the response is malformed, it raises a `ValidationError` instead of silently passing garbage to the next agent.

Code: `backend/app/models/agent_outputs.py`

---

## Project structure

```
agentforge/
├── backend/app/
│   ├── agents/          7 agents (supervisor, investigation, knowledge,
│   │                      debugging, coding, testing, review, human_approval)
│   ├── graph/           LangGraph StateGraph workflow
│   ├── rag/             RAG pipeline (chunking, embeddings, vector store,
│   │                      agentic retrieval with iterative refinement)
│   ├── llm/             Gemini client (the only file that imports google.genai)
│   ├── tools/           Deterministic tools (log parsing, repo search,
│   │                      doc search, test runner, git diff, security)
│   ├── models/          Pydantic models (IncidentState, agent outputs, events)
│   ├── db/              SQLAlchemy ORM (SQLite by default, Postgres via config)
│   ├── api/             FastAPI routes, schemas, app factory
│   └── core/            Config, logging
│
├── frontend/src/
│   ├── components/      Dashboard, IncidentDetail, Timeline, StatusBadge
│   ├── api.js           API client
│   └── App.jsx          Main app (two views, no router needed)
│
├── backend/tests/       131 tests (unit + integration + LangGraph routing)
├── evaluation/          Evaluation harness measuring real fix accuracy
├── knowledge_base/      Markdown docs the RAG pipeline retrieves from
├── sample_project/      Intentionally buggy app that AgentForge investigates
├── scripts/             Demo scripts (investigate_demo.py, rag_demo.py)
├── docs/                Architecture, agent workflow, RAG, security docs
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

---

## Tech stack

| Layer | Technology | Why |
|---|---|---|
| Agent orchestration | LangGraph `StateGraph` | Graph-based workflow with conditional routing and typed state. Makes the multi-agent pipeline explicit and testable. |
| LLM | Google Gemini (`google-genai`) | Structured output support, embedding API, free tier for development |
| RAG vector store | ChromaDB (in-memory) | Rebuilt at startup, no persistence needed for this scale |
| Embeddings | `gemini-embedding-001` | 768 dimensions, supports task-type hints for retrieval |
| Backend | FastAPI | Async, auto-generated OpenAPI docs, minimal boilerplate |
| Database | SQLAlchemy + SQLite | Zero setup default, swap to Postgres with one env var |
| Frontend | React + Vite | Simple SPA with dashboard and incident detail views |
| Validation | Pydantic v2 | Schema enforcement for LLM outputs and API requests |
| Containerization | Docker + Docker Compose | One command to spin up the whole stack |

---

## Getting started

You'll need Python 3.10+, Node.js 18+, and a Gemini API key (free at [Google AI Studio](https://aistudio.google.com/apikey)).

```bash
git clone https://github.com/KoushikN01/AgentForge-agentic-ai.git
cd AgentForge-agentic-ai

# Backend setup
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"

# Environment config
cp .env.example .env
# Open .env and paste your GEMINI_API_KEY
```

### Running locally

```bash
# Terminal 1: backend
cd backend && uvicorn app.main:app --reload
# API at http://localhost:8000, Swagger docs at http://localhost:8000/docs

# Terminal 2: frontend
cd frontend && npm install && npm run dev
# Dashboard at http://localhost:5173
```

Open the dashboard, create an incident, click "Start investigation," watch the agents work through the pipeline, then approve or reject the fix.

### Running with Docker

```bash
docker compose up --build
```

---

## Tests

```bash
# All 131 backend tests (no API key needed, uses a scripted Gemini client)
pytest backend/tests -v

# Evaluation harness (runs all 3 real bugs through the full pipeline)
python evaluation/run_evaluation.py

# Demo investigations
python scripts/investigate_demo.py
python scripts/investigate_demo.py --incident login
python scripts/investigate_demo.py --incident orders-total
```

The tests cover every agent individually, the full LangGraph workflow end to end (including the retry path), the sandbox safety boundary (verifying the real project stays byte-identical until approval), the RAG pipeline, all API endpoints, and the human approval gate.

---

## Evaluation results

The evaluation harness tests against 3 real, intentional bugs in `sample_project/` (not synthetic benchmarks):

| Metric | Result |
|---|---|
| Automated tests passing | 131 / 131 |
| Incidents reaching approval | 3 / 3 |
| Correct file targeted | 3 / 3 |
| Sandbox tests passing after fix | 3 / 3 |

---

## REST API

| Method | Endpoint | What it does |
|---|---|---|
| GET | `/health` | Liveness check |
| POST | `/incidents` | Create an incident (title, description, severity) |
| GET | `/incidents` | List all incidents |
| GET | `/incidents/{id}` | Full state: evidence, root cause, patch, test/review results |
| POST | `/incidents/{id}/investigate` | Start the multi-agent workflow |
| GET | `/incidents/{id}/timeline` | Per-agent workflow events |
| POST | `/incidents/{id}/approve` | Approve or reject the fix |
| GET | `/incidents/{id}/report` | Final structured report |

Swagger UI at `/docs` when the server is running.

---

## What's in the docs/ folder

| File | Content |
|---|---|
| `docs/architecture.md` | System design, request flow, why each tech was chosen |
| `docs/agent-workflow.md` | Every agent: role, inputs/outputs, LLM usage |
| `docs/rag.md` | RAG pipeline in detail: traditional vs agentic, keyword fallback |
| `docs/security.md` | Threat model, controls, what's genuinely not done and why |
| `docs/observability.md` | Timeline events, per-node tracing |
| `docs/interview-guide.md` | 30-second, 2-minute, and 5-minute explanations |

---

## Known limitations

Stating these upfront because I'd rather be honest than have someone find out during a code review:

Every automated test uses a scripted Gemini client (returns realistic structured responses). This verifies the system's logic and safety controls, not Gemini's actual output quality. Run `scripts/investigate_demo.py` with a real API key to see live results.

Docker setup hasn't been tested with an actual Docker daemon (wasn't available in the build environment). The configs are valid YAML, but `docker compose up` hasn't been run.

No API authentication or rate limiting. This is a portfolio project, not a production deployment.

One patch per investigation. The system fixes one bug in one file per run. `sample_project` has 3 distinct bugs, so you'd run 3 separate investigations.

Retries go back to Coding, not Debugging. If the diagnosed root cause itself is wrong, retrying won't help.

---

## About me

I'm a fresher looking for roles in Agentic AI, Generative AI, and LLM application development. This project is how I learn by building. Not a tutorial follow-along; I designed the architecture, implemented the agents, wrote the tests, and built the evaluation harness from scratch.

If you're hiring for anything related to multi-agent systems, RAG, LangGraph, LLM integration, or full-stack AI applications, I'd love to chat.

[GitHub](https://github.com/KoushikN01)

---

If you found this interesting, a star on the repo would mean a lot.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/LangGraph-Multi--Agent-FF6F00?style=for-the-badge&logo=chainlink&logoColor=white" />
  <img src="https://img.shields.io/badge/Google_Gemini-LLM-4285F4?style=for-the-badge&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/React-Frontend-61DAFB?style=for-the-badge&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/ChromaDB-Vector_Store-FF6F61?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
</p>

<h1 align="center">🤖 AgentForge — Multi-Agent AI Incident Investigation System</h1>

<p align="center">
  <strong>An end-to-end Agentic AI system that autonomously investigates software incidents using 7 specialized AI agents, Agentic RAG, a LangGraph orchestration pipeline, and a human-in-the-loop approval workflow.</strong>
</p>

<p align="center">
  <em>Not a toy chatbot wrapper — a production-grade, multi-agent architecture with sandboxed code execution, bounded retry loops, and real test verification.</em>
</p>

---

## 📌 Why This Project Stands Out

> **For recruiters:** This project demonstrates hands-on proficiency in the most in-demand AI/ML skills of 2025-26 — **Agentic AI**, **RAG (Retrieval-Augmented Generation)**, **LangGraph**, **LLM orchestration**, and **full-stack development**. Every component is real, tested, and working — not a tutorial copy-paste.

| What recruiters look for | Where you'll find it in this project |
|---|---|
| **Agentic AI Architecture** | 7 specialized agents orchestrated via LangGraph `StateGraph` |
| **RAG (Retrieval-Augmented Generation)** | Agentic RAG with iterative retrieval, sufficiency checking, and keyword fallback |
| **LangGraph / LangChain Ecosystem** | Full `StateGraph` with conditional routing, retry loops, and state management |
| **LLM Integration (Gemini)** | Structured outputs via Pydantic models, prompt engineering, reflection patterns |
| **Human-in-the-Loop** | Mandatory approval gate before any code touches the real codebase |
| **Full-Stack Development** | FastAPI REST API + React/Vite dashboard + SQLAlchemy + Docker |
| **Testing & Evaluation** | 131 automated tests + evaluation harness measuring real fix accuracy |
| **Safety-First Design** | Sandboxed execution, path traversal guards, bounded retries |

---

## 🧠 What Does This Project Do? (Simple Explanation)

Imagine you're an on-call engineer and a bug report comes in: *"Login endpoint is returning 500 errors"*.

**AgentForge handles the entire investigation automatically:**

```
📋 Bug Report Filed
      ↓
🔍 Investigation Agent — reads logs, greps source code for clues
      ↓
📚 Knowledge Agent (RAG) — searches documentation/runbooks for context
      ↓
🐛 Debugging Agent — diagnoses the root cause with evidence
      ↓
💻 Coding Agent — proposes a code fix (applied ONLY to a sandbox copy)
      ↓
🧪 Testing Agent — runs real pytest tests (not "AI says it looks right")
      ↓
🛡️ Review Agent — reviews the actual diff for risks
      ↓
👤 Human Approval — YOU decide if the fix goes live
```

**The key idea:** AI agents collaborate in a pipeline — each agent does one thing well, passes structured data to the next, and the system never touches your real code until a human explicitly approves.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     React Frontend (:5173)                          │
│          Dashboard  •  Incident Detail  •  Timeline View            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ REST API (fetch + JSON)
┌──────────────────────────────▼──────────────────────────────────────┐
│                    FastAPI Backend (:8000)                           │
│     Routes  •  Schemas  •  SQLAlchemy ORM  •  Background Tasks      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                LangGraph StateGraph Workflow                         │
│                                                                     │
│  ┌────────────┐   ┌───────────────┐   ┌─────────────┐              │
│  │ Supervisor │──▶│ Investigation │──▶│  Knowledge   │              │
│  │            │   │   (Logs/Code) │   │ (Agentic RAG)│              │
│  └────────────┘   └───────────────┘   └──────┬──────┘              │
│                                              │                      │
│  ┌────────────┐   ┌───────────────┐   ┌──────▼──────┐              │
│  │   Review   │◀──│    Testing    │◀──│   Coding    │◀─┐           │
│  │ (Security) │   │  (Real Tests) │   │ (Sandboxed) │  │           │
│  └─────┬──────┘   └───────────────┘   └─────────────┘  │           │
│        │                                                │ retry     │
│        ├── approved + tests pass ──▶ Awaiting Approval  │ (max 2)  │
│        ├── needs retry ─────────────────────────────────┘           │
│        └── retries exhausted ──────▶ Failed                        │
│                                                                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│              Sandbox Workspace (Safety Layer)                       │
│    All code changes happen in a throwaway copy — NEVER the real     │
│    project. Only apply_human_decision() can touch the real code.    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔑 Key Technical Concepts Demonstrated

### 1. 🤖 Agentic AI (Multi-Agent System)

**What it means:** Instead of one monolithic AI doing everything, the workload is split across **7 specialized agents**, each with a focused role, communicating through a shared state.

**How it's implemented:**

| Agent | Role | Uses LLM? |
|---|---|---|
| **Supervisor** | Initializes investigation, routes to first agent | ❌ No |
| **Investigation** | Reads logs + greps source code → summarizes evidence | ✅ 1 call |
| **Knowledge (RAG)** | Retrieves relevant docs from knowledge base | ✅ 0-2 calls |
| **Debugging** | Diagnoses root cause from evidence + context | ✅ 1 call |
| **Coding** | Proposes a fix (sandboxed, with reflection on retries) | ✅ 1 call |
| **Testing** | Runs real `pytest` suite — no LLM, actual test execution | ❌ No |
| **Review** | Reviews the real `git diff` + test results for risks | ✅ 1 call |

📁 **Code:** [`backend/app/agents/`](backend/app/agents/)

---

### 2. 📚 RAG — Retrieval-Augmented Generation

**What it means:** Instead of relying solely on the LLM's training data, the system retrieves relevant documentation from a knowledge base to ground its diagnosis in facts.

**Two RAG strategies implemented:**

#### Traditional RAG (Baseline)
```
Incident Description → Embed → Vector Search → Top-K Chunks → Answer
```

#### Agentic RAG (Default — What Makes This Advanced)
```
Incident Description
       ↓
Gemini decides WHAT to search for (RetrievalPlan)
       ↓
Vector search with those queries (ChromaDB)
       ↓
Gemini evaluates: "Is this enough?" (SufficiencyCheck)
       ↓
  ├── Yes → Proceed to Debugging Agent
  └── No  → Refine search queries → Another round (max 2 rounds)
```

**Why Agentic RAG is better:** A login error shouldn't just search for "login" — it should also search for "environment variables" and "JWT configuration." The LLM intelligently decides what to retrieve.

**Fallback mechanism:** If Gemini API fails, the system automatically falls back to keyword-based search — zero downtime, fully transparent.

📁 **Code:** [`backend/app/rag/agentic_retrieval.py`](backend/app/rag/agentic_retrieval.py) · [`backend/app/agents/knowledge.py`](backend/app/agents/knowledge.py)

---

### 3. 🔄 LangGraph — Agent Orchestration Framework

**What it means:** LangGraph (from the LangChain ecosystem) provides a graph-based framework to orchestrate multi-agent workflows with state management, conditional routing, and retry logic.

**How it's used:**

```python
# The actual workflow graph (simplified from backend/app/graph/workflow.py)
graph = StateGraph(IncidentState)

# Add agent nodes
graph.add_node("supervisor", supervisor.start_investigation)
graph.add_node("investigation", investigation.build_investigation_node(...))
graph.add_node("knowledge", knowledge.build_knowledge_node(...))
graph.add_node("debugging", debugging.build_debugging_node(...))
graph.add_node("coding", coding.build_coding_node(...))
graph.add_node("testing", testing.build_testing_node(...))
graph.add_node("review", review.build_review_node(...))

# Conditional routing after review — the key LangGraph feature
graph.add_conditional_edges(
    "review",
    route_after_review,  # Returns "approve", "retry", or "fail"
    {"approve": "awaiting_approval", "retry": "coding", "fail": "failed"}
)
```

**Key LangGraph concepts demonstrated:**
- **`StateGraph`** — Typed state shared across all agents (`IncidentState`)
- **Conditional edges** — Review agent routes to approval, retry, or failure
- **Bounded retry loop** — Coding → Testing → Review → (retry) with `MAX_RETRIES = 2`
- **State accumulation** — Each agent reads previous agents' outputs and adds its own

📁 **Code:** [`backend/app/graph/workflow.py`](backend/app/graph/workflow.py)

---

### 4. 🔁 Reflection & Retry Pattern

**What it means:** When a fix fails tests or review, the Coding Agent doesn't blindly retry — it receives feedback on WHY the previous attempt failed and adjusts.

```python
# From backend/app/agents/coding.py — retry with reflection
if is_retry:
    feedback = f"Tests: {state.test_result.summary} | Review: {state.review_result.concerns}"
    prompt += f"\nPrevious fix failed: {feedback}\nPropose a DIFFERENT fix.\n"
```

This mirrors how real engineers iterate — learn from failure, don't repeat it.

---

### 5. 🛡️ Safety & Sandboxing

A critical design principle: **the LLM is not malicious, but it IS wrong sometimes.** The system stays safe even when the AI makes mistakes.

| Safety Control | Implementation |
|---|---|
| **Sandbox execution** | All patches applied to a temp copy, never the real project |
| **Path traversal guard** | `security.py` prevents `../../etc/passwd` style attacks |
| **Patch validation** | Original snippet must match exactly once, or the patch is rejected |
| **Real test execution** | `pytest` runs actual tests — no "LLM says it looks right" |
| **Bounded retries** | `MAX_RETRIES = 2` — the loop physically cannot run forever |
| **Human approval gate** | `apply_human_decision()` is the ONLY path to modify real code |

📁 **Code:** [`backend/app/agents/workspace.py`](backend/app/agents/workspace.py) · [`backend/app/tools/security.py`](backend/app/tools/security.py)

---

### 6. 📊 Structured LLM Outputs (Pydantic)

Every LLM call returns structured, validated data — not raw text that might break downstream agents:

```python
class RootCauseAnalysis(BaseModel):
    root_cause: str              # What's actually broken
    confidence: float            # How confident (0-1)
    supporting_evidence: list[str]  # What evidence supports this

class PatchProposal(BaseModel):
    target_file: str             # Which file to patch
    original_snippet: str        # Exact code to find
    replacement_snippet: str     # What to replace it with
    explanation: str             # Why this fixes the issue
```

If Gemini returns malformed JSON, Pydantic raises a `ValidationError` — the system never silently processes bad data.

📁 **Code:** [`backend/app/models/agent_outputs.py`](backend/app/models/agent_outputs.py)

---

## 🗂️ Project Structure

```
AgentForge/
├── 🐍 backend/app/
│   ├── agents/          # 7 AI agents (supervisor, investigation, knowledge,
│   │                    #   debugging, coding, testing, review, human_approval)
│   ├── graph/           # LangGraph StateGraph workflow orchestration
│   ├── rag/             # RAG pipeline (chunking, embeddings, vector store,
│   │                    #   agentic retrieval with iterative refinement)
│   ├── llm/             # Gemini client (only file importing google.genai)
│   ├── tools/           # Deterministic tools (log parsing, repo search,
│   │                    #   doc search, test runner, git diff, security)
│   ├── models/          # Pydantic models (IncidentState, agent outputs, events)
│   ├── db/              # SQLAlchemy ORM (SQLite/Postgres)
│   ├── api/             # FastAPI routes, schemas, app factory
│   └── core/            # Config, logging
│
├── ⚛️  frontend/src/
│   ├── components/      # Dashboard, IncidentDetail, Timeline, StatusBadge
│   ├── api.js           # API client
│   └── App.jsx          # Main app (two-view SPA)
│
├── 🧪 backend/tests/    # 131 tests (unit + integration + LangGraph routing)
├── 📊 evaluation/       # Evaluation harness (measures real fix accuracy)
├── 📚 knowledge_base/   # Markdown docs the RAG pipeline retrieves from
├── 🐛 sample_project/   # Intentionally-buggy app that AgentForge investigates
├── 📜 scripts/          # Demo scripts (investigate_demo.py, rag_demo.py)
├── 📖 docs/             # Architecture, agent workflow, RAG, security, observability
├── 🐳 Dockerfile        # Backend container
├── 🐳 docker-compose.yml# Full stack orchestration
└── ⚙️  pyproject.toml    # Project config & dependencies
```

---

## ⚙️ Tech Stack

| Layer | Technology | Why This Choice |
|---|---|---|
| **Agent Orchestration** | **LangGraph** `StateGraph` | Graph-based workflow with conditional routing, retry loops, and typed state — makes the multi-agent pipeline explicit and testable |
| **LLM** | **Google Gemini** (`google-genai`) | Structured output support, embedding API, free tier available |
| **RAG Vector Store** | **ChromaDB** | In-memory vector store, rebuilt at startup — simple and sufficient for this scale |
| **Embeddings** | **Gemini Embedding** (`gemini-embedding-001`) | 768-dimension embeddings with task-type hints (RETRIEVAL_DOCUMENT vs RETRIEVAL_QUERY) |
| **Backend API** | **FastAPI** | Async-native, auto-generated OpenAPI docs, minimal boilerplate |
| **Database** | **SQLAlchemy** + SQLite (Postgres-ready) | Zero-setup default, one env var swap to Postgres |
| **Frontend** | **React** + **Vite** | Lightweight SPA (dashboard + incident detail + timeline) |
| **Validation** | **Pydantic v2** | Structured LLM outputs, request/response schemas, state models |
| **Containerization** | **Docker** + **Docker Compose** | One-command deployment of backend + frontend |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- A Gemini API key (free at [Google AI Studio](https://aistudio.google.com/apikey))

### Installation

```bash
# Clone the repository
git clone https://github.com/KoushikN01/AgentForge-agentic-ai.git
cd AgentForge-agentic-ai

# Set up the backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env → paste your GEMINI_API_KEY
```

### Run Locally

```bash
# Terminal 1 — Backend API
cd backend && uvicorn app.main:app --reload
# API at http://localhost:8000 | Swagger docs at http://localhost:8000/docs

# Terminal 2 — Frontend
cd frontend && npm install && npm run dev
# Dashboard at http://localhost:5173
```

### Run with Docker

```bash
docker compose up --build
# Backend → http://localhost:8000 | Frontend → http://localhost:5173
```

---

## 🧪 Testing

```bash
# Run all 131 backend tests (no API key needed — uses scripted Gemini)
pytest backend/tests -v

# Run the evaluation harness (measures real fix accuracy)
python evaluation/run_evaluation.py

# Run demo investigations
python scripts/investigate_demo.py                   # Full workflow
python scripts/investigate_demo.py --incident login  # Specific bug
```

### What the tests cover:
- ✅ Every agent individually (unit tests)
- ✅ Full LangGraph workflow end-to-end (integration tests)
- ✅ Retry loop and routing logic
- ✅ Sandbox safety boundary (real project stays untouched until approval)
- ✅ RAG pipeline (chunking, vector store, agentic retrieval)
- ✅ API endpoints (create, investigate, approve, reject)
- ✅ Human approval gate (asserts real project is byte-identical until approved)

---

## 🌐 REST API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/incidents` | Create an incident (`title`, `description`, `severity`) |
| `GET` | `/incidents` | List all incidents |
| `GET` | `/incidents/{id}` | Full incident state (evidence, root cause, patch, tests, review) |
| `POST` | `/incidents/{id}/investigate` | Start the multi-agent investigation workflow |
| `GET` | `/incidents/{id}/timeline` | Per-agent workflow events |
| `POST` | `/incidents/{id}/approve` | Approve or reject the proposed fix (`{"approved": true/false}`) |
| `GET` | `/incidents/{id}/report` | Final structured investigation report |

Full Swagger UI available at `/docs` when the server is running.

---

## 📈 Evaluation Results

The evaluation harness tests against **3 real, intentional bugs** in the sample project (not synthetic benchmarks):

| Metric | Result |
|---|---|
| Automated tests passing | **131 / 131** |
| Incidents reaching approval | **3 / 3** |
| Correct file targeted | **3 / 3** |
| Sandbox tests passing after fix | **3 / 3** |

---

## 🎯 Skills Demonstrated

This project is specifically designed to demonstrate proficiency in:

```
┌─────────────────────────────────────────────────────┐
│                 Agentic AI & Gen AI                  │
├─────────────────────────────────────────────────────┤
│  ✦ Multi-Agent Systems (7 specialized agents)       │
│  ✦ LangGraph (StateGraph, conditional routing)      │
│  ✦ RAG (Agentic retrieval + fallback strategies)    │
│  ✦ Prompt Engineering (structured outputs)          │
│  ✦ Reflection & Retry Patterns                      │
│  ✦ Human-in-the-Loop Workflows                      │
│  ✦ LLM Safety & Sandboxing                          │
│  ✦ Vector Embeddings (ChromaDB + Gemini)            │
│  ✦ Evaluation Harness (real accuracy measurement)   │
├─────────────────────────────────────────────────────┤
│              Full-Stack Engineering                   │
├─────────────────────────────────────────────────────┤
│  ✦ Python (FastAPI, SQLAlchemy, Pydantic v2)        │
│  ✦ React + Vite (Dashboard, Timeline, Detail views) │
│  ✦ REST API Design (12 endpoints, OpenAPI docs)     │
│  ✦ Docker & Docker Compose                          │
│  ✦ Test-Driven Development (131 tests, pytest)      │
│  ✦ Security (path traversal guards, sandbox)        │
└─────────────────────────────────────────────────────┘
```

---

## 📖 Documentation

| Document | What it covers |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | System design, request flow, why each technology was chosen |
| [`docs/agent-workflow.md`](docs/agent-workflow.md) | Every agent explained — role, inputs/outputs, LLM usage |
| [`docs/rag.md`](docs/rag.md) | RAG pipeline: traditional vs agentic, keyword fallback |
| [`docs/security.md`](docs/security.md) | Threat model, controls table, what's NOT done (and why) |
| [`docs/observability.md`](docs/observability.md) | Timeline events, per-node tracing |
| [`docs/interview-guide.md`](docs/interview-guide.md) | 30-sec / 2-min / 5-min explanations for interviews |

---

## 🤝 About the Developer

I'm a fresher passionate about **Agentic AI** and **Generative AI**, actively seeking roles in:
- 🤖 AI/ML Engineer
- 🧠 Gen AI Developer
- 🔧 LLM Application Developer
- 🏗️ AI Platform Engineer

This project represents my understanding of real-world AI agent architectures — not a tutorial follow-along, but a ground-up implementation demonstrating how multi-agent systems, RAG pipelines, and LLM orchestration work together to solve real problems.

**Let's connect:** [GitHub](https://github.com/KoushikN01) 

---

## 📄 License

This project is open-source and available for educational and demonstration purposes.

---

<p align="center">
  <strong>⭐ If you found this project interesting, please consider starring the repository!</strong>
</p>

# BUILD_VERIFICATION.md — FINAL STATUS (read this first)

This is the single source of truth for what is actually verified in
AgentForge. Everything below "## Phase 1" is the detailed, chronological
build log (kept because it's accurate and shows real work, including real
mistakes found and fixed along the way) - this section is the current,
authoritative summary. Where the two ever seem to disagree, this section
wins.

**Environment this was built and verified in**: no Docker daemon, no
`GEMINI_API_KEY`, no network access beyond PyPI/npm/GitHub. Every
"NOT VERIFIED" below is NOT VERIFIED because of that, not because the
work wasn't done - and every one of them has an exact command for you to
run yourself with what this environment lacked.

## VERIFIED (actually executed, in this environment, before packaging)

- **Full backend test suite**: `pytest backend/tests -v` → **131 passed**,
  from a clean `pip install -e ".[dev]"` in a throwaway venv (not just
  `PYTHONPATH` tricks) - this also verified the package installs
  correctly, which an earlier, unverified assumption had gotten wrong
  (see "Found and fixed" below).
- **`sample_project`'s own tests**: 3 failed, 4 passed - the correct,
  unmodified, intentional bug state. `git status` on `sample_project`
  confirmed clean (no accidental edits) both before and after every test
  run in this session.
- **Every agent individually**, with Gemini scripted: supervisor,
  investigation (real log/code evidence gathering), knowledge (both
  `vector` and `keyword` `RAG_MODE`), debugging, coding (real sandbox
  patching, including a patch that genuinely fails to apply), testing
  (real pytest subprocess), review, human approval (real file copy on
  approve, real no-op on reject).
- **The compiled LangGraph workflow**, streamed and inspected node-by-
  node: the happy path, the retry path (with real reflection feedback in
  the second prompt), the bounded-failure path (exactly `MAX_RETRIES + 1`
  coding attempts, never more), and that a full run against the real,
  shipped `sample_project` leaves every shipped file byte-identical.
- **The full FastAPI API**, via `TestClient` against a real in-memory
  SQLite database and a real sandboxed copy of `sample_project`: create,
  investigate (as a real background task), poll, the retry path through
  the API, double-investigate rejected (409), approve-before-ready
  rejected (409), 404s, listing, and a crash during investigation
  recorded as `failed` with its real error message rather than lost.
- **The workflow-events timeline**: `GET /incidents/{id}/timeline`
  returns one real, timed event per node actually run, including the
  terminal `awaiting_approval` node.
- **The evaluation harness**, run fresh immediately before packaging (no
  API key → scripted/"mock" mode): all 3 of `sample_project`'s real bugs
  → correct patch target, sandbox tests fully passing, 0 retries needed.
  Output: `evaluation/results/mock_run.json`.
- **Both demo scripts' no-API-key path** (`scripts/investigate_demo.py`,
  `scripts/rag_demo.py`): both fail with a clear, correct message and
  exit cleanly - neither crashes or fakes a result.
- **The frontend genuinely compiles**: `npm install && npm run build`
  succeeded (36 modules transformed, real production bundle written).
- **`docker-compose.yml` is valid YAML** (parsed with PyYAML) with the
  `api` and `frontend` services both present and correctly configured.
- **Security/quality static audit**, run for real, not asserted: no
  hardcoded absolute paths, no `TODO`/`FIXME`, no bare `except:`/fake
  `return True` stubs, all 46 non-`main` backend modules import cleanly,
  `app.main` imports and serves all 10 real `/incidents...` routes
  correctly (confirmed via `TestClient`, not just a route listing), a
  targeted grep for `api_key`/`secret`/`password` across `backend/app`
  and `frontend/src` found only config plumbing and comments explaining
  *not* to log the key - no literal secret values, and no `.env` file
  exists anywhere in the project tree.
- **Fresh-environment re-verification**: the packaged ZIP was extracted
  into a brand-new directory and `pytest`, `sample_project`'s tests, and
  the evaluation harness were all re-run there - not just in the working
  directory - with identical results to the above.

## NOT VERIFIED (and exactly how to verify it yourself)

- **Live Gemini** - reasoning quality, real embeddings, real structured
  outputs. No API key was available anywhere in this build environment.
  Run `python evaluation/run_evaluation.py` or
  `python scripts/investigate_demo.py` with `GEMINI_API_KEY` set.
- **Docker build/run** - no Docker daemon was available
  (`docker: not found`). Dockerfiles were reviewed by hand and the
  compose file's YAML was validated, but `docker build`/`docker compose
  up` have never actually executed. Run `docker compose up --build`.
- **The frontend's actual rendered behavior in a browser** - `npm run
  build` proves the code compiles (every import resolves, JSX is valid),
  not that clicking through it looks or feels right. Run `npm run dev`
  with a real backend and look at it.
- **Postgres as `DATABASE_URL`** - only SQLite has actually been run
  against. The code path is provider-agnostic (plain SQLAlchemy), but
  that claim itself is untested against a real Postgres instance.

## NOT APPLICABLE (genuinely out of this project's intended scope)

- Authentication/authorization on the API, rate limiting, DB migrations
  tooling, multi-tenant sandboxing below the OS level, a persistent
  vector store, a task queue. Each is a legitimate production-hardening
  concern, documented as deliberately absent (not forgotten) in
  `docs/security.md` and `README.md`'s "Known limitations" - adding any
  of them would be scope creep beyond a learning project demonstrating
  agentic-AI architecture, not a gap in the intended design.

## Found and fixed during this final audit

- **`pip install -e ".[dev]"`** - the exact command every phase's README
  has told users to run - **actually failed** (`error: Multiple
  top-level packages discovered in a flat-layout`) the first time it was
  genuinely tested in a clean venv rather than assumed to work from
  `PYTHONPATH`-based test runs. Root cause: `pyproject.toml` had no
  package-discovery config, so setuptools saw `backend/`, `frontend/`,
  `evaluation/`, `sample_project/`, `knowledge_base/` all at the project
  root and refused to guess. Fixed with an explicit
  `[tool.setuptools] package-dir` + `[tool.setuptools.packages.find]
  where = ["backend"]`. Re-verified in a fresh venv: installs cleanly,
  `app` imports from the installed package (not just `PYTHONPATH`), and
  all 131 tests pass against that install.
- **A test in the inherited work had an incomplete assertion**
  (`test_timeline_reports_one_completed_event_per_node` expected 7
  timeline nodes on the happy path; the graph genuinely and correctly
  runs 8, including the terminal `awaiting_approval` node - true and
  tested since Phase 4's `test_graph_integration.py`). The
  implementation was correct; the test's expected list was missing one
  real entry. Fixed the assertion, not the behavior.
- **A mock in `evaluation/run_evaluation.py`** initially returned exactly
  one embedding vector regardless of how many chunks were passed in,
  breaking ingestion (`Got 16 chunks but 1 embeddings`) on every
  incident. Fixed to return one vector per input text; re-ran and got
  the real output quoted above.

---

# BUILD_VERIFICATION.md — Phase 1

## What was implemented

- `app/core/config.py` — `Settings` dataclass + `load_settings()`, reads
  `GEMINI_API_KEY`, `GEMINI_MODEL` (default `gemini-2.5-flash`), `LOG_LEVEL`
  (default `INFO`) from environment variables via `python-dotenv`.
- `app/core/logging_config.py` — `setup_logging()` / `get_logger()`.
- `app/llm/gemini.py` — `GeminiClient` wrapping the official `google-genai`
  SDK (`pip install google-genai`, `from google import genai`), with
  `generate_text()` and `generate_structured()`, and two custom exceptions
  (`GeminiConfigError`, `GeminiRequestError`).
- `app/models/incident_state.py` — `Severity`, `IncidentStatus`, `Incident`,
  `IncidentState` (Pydantic v2 models).
- `app/models/triage.py` — `IncidentTriage`, a small schema for
  structured-output demonstration.
- 15 tests across `test_config.py`, `test_gemini_client.py`,
  `test_incident_state.py`.

## What was actually tested, and how

Run yourself with: `pip install -e ".[dev]"` then `pytest -v`.

- **`load_settings()`** — tested for real (no mocking) using `monkeypatch`
  to set/unset environment variables. This genuinely exercises the code.
- **Pydantic models** (`Incident`, `IncidentState`) — tested for real:
  default values, validation errors on missing/invalid fields, message
  list behavior. No mocking involved; this is real Pydantic validation.
- **`GeminiClient` missing-API-key error path** — tested twice: once
  through pytest (`test_raises_config_error_when_no_api_key`), and once
  manually outside pytest by unsetting `GEMINI_API_KEY` and constructing a
  real (non-mocked) `GeminiClient`, confirming it raises `GeminiConfigError`
  with the expected message. This path is genuinely verified end-to-end.
- **`GeminiClient.generate_text` / `generate_structured`** (the parts that
  build a request and parse a response) — tested with `google.genai.Client`
  fully **mocked** (`unittest.mock.patch`). These tests confirm: the right
  model name and prompt are passed to `generate_content`; a returned JSON
  string gets correctly parsed and validated into the requested Pydantic
  model; SDK exceptions get wrapped into `GeminiRequestError`; an empty
  response raises `GeminiRequestError`; malformed JSON from Gemini raises
  a validation error instead of silently returning bad data.
- I also confirmed by inspecting the installed `google-genai` package
  directly in this environment (not from memory/training data) that
  `genai.Client(api_key=...)`, `client.models.generate_content(model=...,
  contents=..., config=...)`, and `types.GenerateContentConfig` fields
  `system_instruction`, `response_mime_type`, `response_schema` all exist
  with the signatures this code uses.

## What was NOT tested / could not be tested here

- **A real call to the live Gemini API.** I do not have a Gemini API key
  and this environment has no network access to Google's API, only to a
  short allowlist of package registries (PyPI, npm, GitHub, etc.). So
  `GeminiClient` has never actually talked to Gemini — only to a mock.
  **You should run one real call yourself** once you add your key to
  `.env`, e.g.:
  ```python
  from app.llm.gemini import GeminiClient
  print(GeminiClient().generate_text("Say hello in one sentence."))
  ```
  If that fails, it's almost certainly the API key, model name
  availability for your account, or a network/proxy issue on your machine
  — not the wrapper code itself (which the mocked tests do cover).
- Whether `gemini-2.5-flash` specifically is the ideal default for your
  use case/account — I picked it because it's Google's current stable,
  generally-available model as of this environment's last web search, not
  because I ran a live comparison against other models.

## First commands to run (Phase 1)

```bash
cd agentforge
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env    # then paste in your real GEMINI_API_KEY
pytest -v
```

---

# Phase 2

## What was implemented

- `app/tools/models.py`, `security.py`, `repo_tools.py`, `log_tools.py`,
  `doc_tools.py`, `test_tools.py`, `git_tools.py` — five deterministic
  tools plus their shared result types and path-safety guardrail.
- `sample_project/` — a small FastAPI app (`app/main.py`, `auth.py`,
  `orders.py`, `users.py`) with 3 intentional bugs, its own pytest suite
  (`tests/`), a synthetic log file (`logs/app.log`), and its own git repo.
- `knowledge_base/` — 5 markdown docs plus `incidents/` with one past
  incident write-up.
- `docs/sample-project-bugs.md` — what's broken and why, kept outside the
  tool-accessible roots.
- 25 new tests across `test_repo_tools.py`, `test_log_tools.py`,
  `test_doc_tools.py`, `test_test_tools.py`, `test_git_tools.py`.

## What was actually tested, and how

- **All 25 new tool tests, plus all 15 Phase 1 tests, run together for
  real**: `pytest backend/tests/` → **40 passed**, in this environment,
  right before packaging. Nothing here is asserted from memory — I ran
  it and this is the real output:
  ```
  40 passed in 1.29s
  ```
- **`repo_tools`, `log_tools`, `doc_tools`** — tested against real
  temporary directories/files created per-test (pytest's `tmp_path`), not
  mocks. Path-traversal rejection (`PathSecurityError`) is tested for
  real, not simulated.
- **`test_tools.run_tests`** — tested by actually spawning a real
  `python -m pytest` subprocess against a throwaway toy project written
  to `tmp_path`, and separately confirmed for real against the actual
  `sample_project/` (see integration check below). Not mocked.
- **`git_tools.get_diff`** — tested against a real git repository
  initialized with real `git` subprocess calls in the test itself
  (`git init`, `git commit`, then edit a file and diff). Not mocked. Also
  confirmed `NotAGitRepositoryError` is raised for a real non-git
  directory.
- **`sample_project`'s bugs are genuine and fixable** — I ran its test
  suite as shipped:
  ```
  FAILED tests/test_auth.py::test_login_with_valid_credentials_returns_a_token
  FAILED tests/test_orders.py::test_get_order_total_includes_sales_tax
  FAILED tests/test_orders.py::test_get_nonexistent_order_returns_404
  3 failed, 4 passed in 0.32s
  ```
  then temporarily applied the real fix for all three bugs (renamed the
  env var lookup, applied the tax multiplier, caught `KeyError` and
  re-raised as `OrderNotFoundError`) and re-ran:
  ```
  7 passed in 0.29s
  ```
  then reverted the fixes before packaging the ZIP. `sample_project`, as
  shipped, is back in its intentionally-buggy state (3 failed, 4 passed —
  confirmed once more after reverting).
- **End-to-end integration check** — ran all five tools for real against
  the actual `sample_project/` and `knowledge_base/` directories (not
  test fixtures) in one script: `repo_tools.search_repository` found the
  `JWT_SECRET_KEY` string in both `app/auth.py` and `tests/test_auth.py`;
  `log_tools` parsed 14 real log entries and found 3 real `ERROR` lines;
  `doc_tools.search_docs` found 4 real docs mentioning `JWT_SECRET`;
  `test_tools.run_tests` reported the real 4-passed/3-failed result
  against `sample_project`; `git_tools.get_diff` reported no changes
  against the real, clean `sample_project` git repo. This confirms the
  tools layer genuinely works against the real deliverable, not just
  synthetic test fixtures.
- **Gemini SDK method signatures** — re-confirmed unchanged from Phase 1
  (no changes to `app/llm/gemini.py` in this phase).

## What was NOT tested / could not be tested here

- **No agent or LLM reasoning exists yet in Phase 2** — the tools are
  plain Python with zero Gemini calls, by design (see spec section on
  cost awareness / deterministic vs. LLM work). So there is nothing
  Gemini-related to newly verify in this phase beyond what Phase 1
  already covers.
- **`sample_project/logs/app.log` is synthetic, hand-written sample
  data** — it was not captured from a real running instance of the app
  (timestamps, request IDs, and error text were written to be realistic
  and internally consistent with the actual bugs, not recorded from an
  actual request). It is clearly documented as synthetic wherever it's
  referenced. If you want real captured logs later, running
  `sample_project` with `uvicorn` and hitting its endpoints would produce
  them.
- **`test_tools.run_tests`'s 60-second timeout** was not stress-tested
  against a genuinely slow or hanging test suite — only against small,
  fast toy suites and the real (fast) `sample_project` suite.

## First commands to run (Phase 2)

```bash
# AgentForge's own tools + Phase 1 (should all be green):
cd agentforge
pip install -e ".[dev]"
pytest -v

# sample_project's own suite (the buggy target app — 3 failed is expected):
cd sample_project
pip install -r requirements.txt
pytest -v
```

---

# Phase 3

## What was implemented

- `app/core/config.py` — added `gemini_embedding_model` setting
  (`GEMINI_EMBEDDING_MODEL`, default `gemini-embedding-001`).
- `app/llm/gemini.py` — added `GeminiClient.embed_texts(texts, task_type)`.
  No other file imports `google.genai` — that invariant from Phase 1 is
  unchanged.
- `app/rag/models.py`, `chunking.py`, `vector_store.py`, `ingest.py`,
  `retrieval.py`, `agentic_retrieval.py` — the RAG pipeline.
- `pyproject.toml` — added `chromadb` dependency.
- `scripts/rag_demo.py` — end-to-end demo script (needs a real API key to
  run).
- 25 new tests across `test_chunking.py`, `test_vector_store.py`,
  `test_embeddings.py`, `test_ingest.py`, `test_retrieval.py`,
  `test_agentic_retrieval.py`, plus 2 new tests in `test_config.py` for
  the embedding-model setting.

## What was actually tested, and how

- **All 65 tests (Phase 1 + 2 + 3) run together for real**, right before
  packaging:
  ```
  65 passed in 1.81s
  ```
- **`chunking.chunk_text`** — pure deterministic tests, no mocking:
  paragraph grouping, splitting at the size boundary, blank input, stable
  chunk IDs.
- **`vector_store`** — tested against a **real, in-memory Chroma
  collection** (not mocked) with small hand-made embedding vectors
  (2D, e.g. `[1.0, 0.0]` vs `[-1.0, 0.0]`) chosen so the "closer" vector
  is unambiguous. This genuinely exercises Chroma's storage and
  similarity search, including confirming the closer match is returned
  first and with a smaller `distance`.
- **`GeminiClient.embed_texts`** — tested with `google.genai.Client` fully
  **mocked**, same pattern as Phase 1's `generate_text`/`generate_structured`
  tests: confirms the right model name, input list, `task_type`, and
  `output_dimensionality=768` are sent, and that SDK errors/empty
  responses are wrapped into `GeminiRequestError`.
- **`ingest.build_chunks` / `ingest_knowledge_base`** — `build_chunks`
  (reading + chunking real files via `doc_tools`) is tested for real
  against a `tmp_path` knowledge base. `ingest_knowledge_base` additionally
  mocks `GeminiClient.embed_texts` (a stub returning a deterministic
  vector per text) and confirms the resulting Chroma collection's chunk
  count matches, and that `embed_texts` was called with
  `task_type="RETRIEVAL_DOCUMENT"`.
- **`retrieval.semantic_search`** — real Chroma collection pre-populated
  with hand-made embeddings, mocked `embed_texts` returning a query vector
  close to one specific chunk; confirms that chunk comes back and that
  `embed_texts` was called with `task_type="RETRIEVAL_QUERY"`.
- **`agentic_retrieval.agentic_retrieve`** — the LOOP LOGIC is tested with
  a mocked `GeminiClient` whose `generate_structured` returns a scripted
  sequence of `RetrievalPlan`/`SufficiencyCheck` objects: confirmed it (1)
  stops after one round when sufficient, (2) runs a second round and
  passes the first round's `missing_information` into the second round's
  prompt when insufficient, and (3) never exceeds `MAX_ROUNDS=2` even if
  sufficiency is never reached. The vector store used underneath is real.
- **End-to-end integration check against the REAL `knowledge_base/`
  directory** (not test fixtures): chunked all 7 real documents into 16
  chunks, ingested them into a real Chroma collection using a stub
  embedding function (deterministic, keyword-presence-based — not a real
  Gemini call), ran `semantic_search` for a login-500-style query and
  confirmed it returned `architecture.md` and `deployment_notes.md`
  (both genuinely relevant), and ran the full `agentic_retrieve` loop
  with scripted plan/sufficiency responses, confirming it correctly
  stopped after one round and returned evidence from the right documents.
  This proves the pipeline's plumbing is correct end to end against the
  real deliverable — the one thing it does NOT prove is what a *real*
  Gemini call would decide to search for or judge as sufficient (see
  below).
- **Current Gemini embedding model name** — confirmed via a fresh web
  search (not from training memory) that `gemini-embedding-001` is the
  current generally-available text embedding model, and that its
  predecessor `text-embedding-004` was deprecated. Also confirmed via
  direct inspection of the installed `google-genai` package (not
  documentation) that `client.models.embed_content(model=, contents=,
  config=)`, `types.EmbedContentConfig(task_type=, output_dimensionality=)`,
  and `response.embeddings[i].values` all exist with the signatures this
  code uses.

## What was NOT tested / could not be tested here

- **No real Gemini embedding call was ever made.** I have no API key and
  no network path to Google's API in this environment (only a short
  allowlist of package registries). Every embedding used in testing is
  either hand-made (vector_store tests) or a mocked/stubbed return value
  (everything else). This means: the actual semantic quality of real
  Gemini embeddings on this knowledge base — e.g., whether `"why is
  login broken"` really does embed closer to `deployment_notes.md` than
  to `troubleshooting_guide.md`'s orders section — is UNVERIFIED. The
  pipeline's plumbing is proven correct; the retrieval *quality* with
  real embeddings is not.
- **No real Gemini `generate_structured` call was made for
  `RetrievalPlan` or `SufficiencyCheck`.** Whether Gemini actually
  proposes good search queries or makes a sound sufficiency judgment for
  a real incident is unverified — only that the surrounding loop logic
  handles whatever structured response it gets.
- **`scripts/rag_demo.py` has never been run end-to-end with a real API
  key** in this environment. I did verify its no-API-key failure path
  works correctly (prints a clear message and exits, doesn't crash).
  **You should run this yourself** once your key is in `.env`:
  ```bash
  python scripts/rag_demo.py
  ```
- **Chroma's in-memory client** was only tested with a handful of chunks
  (16, from the real knowledge base). Its behavior at a much larger scale
  wasn't tested — not relevant yet at this project's size, but worth
  knowing if the knowledge base grows substantially.

## First commands to run (Phase 3)

```bash
cd agentforge
pip install -e ".[dev]"
pytest -v                       # 65 tests, all should pass, no API key needed

# then, with a real GEMINI_API_KEY in .env:
python scripts/rag_demo.py
```

---

# Phase 4

## What was built

- `app/models/agent_outputs.py` - structured output schemas for the agents.
- `app/models/incident_state.py` - extended with `evidence`, `knowledge_context`, `root_cause`,
  `patch_proposal`, `test_result`, `review_result`, `retry_count`, `retry_feedback`, and the
  `AWAITING_APPROVAL` status.
- `app/agents/` - workspace (sandbox), supervisor, investigation, knowledge, debugging, coding,
  testing, review, human_approval.
- `app/graph/workflow.py` - the LangGraph `StateGraph` (LangGraph 1.2.x, Pydantic state schema).
- `scripts/investigate_demo.py` - end-to-end demo with an interactive approval prompt.
- `langgraph` added to `pyproject.toml`.

## What was actually tested (real runs in this environment)

```
pytest backend/tests        -> 101 passed
sample_project/ own tests   -> 3 failed, 4 passed (the intentional bug state; git status clean)
```

Phase 4 added 36 tests (65 -> 101):

| File | Tests | What it proves |
|------|-------|----------------|
| `test_workspace.py` | 11 | Sandbox copy is independent; patch applies once or fails loudly; path traversal rejected; diff; copy-back |
| `test_agents_unit.py` | 14 | Each agent node against a real sandbox (real tools, real patching, real pytest); Gemini mocked |
| `test_graph_integration.py` | 7 | The **compiled** graph's real routing (see below) |
| `test_demo_setup.py` | 4 | The demo's project preparation leaves exactly one real bug per incident |

The integration tests stream the compiled graph and record which nodes ran:

- Happy path visits exactly `supervisor, investigation, knowledge, debugging, coding, testing, review, awaiting_approval`.
- Retry path visits `... coding, testing, review, coding, testing, review, awaiting_approval`, and the
  second coding prompt contains the reflection feedback.
- Retries are bounded: a Gemini that always proposes a bad patch ends in `failed` after exactly
  `MAX_RETRIES + 1` coding attempts.
- Before approval the real project is byte-identical; only the sandbox changed.
- After `apply_human_decision(approved=True)` the real project's tests go from failing to all passing;
  with `approved=False` it is untouched.
- Running the graph against the shipped `sample_project` leaves every shipped file unchanged.

Sandbox fixes and pytest runs are real: the Test Agent spawns a real `pytest` subprocess.

## What uses mocked Gemini

Every Gemini call in all Phase 4 tests goes through a scripted fake client that returns canned
structured answers (a correct patch, a bad patch, a review that approves only if the real test
run had 0 failures). Chroma, the tools, the sandbox, patch application, LangGraph routing and
pytest execution are real.

## What requires your real Gemini API key (NOT verified)

- Whether real Gemini produces a valid `PatchProposal` whose `original_snippet` matches the file
  exactly (this is the most likely real-world failure point).
- Whether real Gemini's root-cause analysis, sufficiency checks and reviews are any good.
- The quality of real Gemini embeddings on this knowledge base.
- `scripts/investigate_demo.py` end to end. I only verified its no-API-key path (clear message,
  clean exit) and its project-setup helper. Run it yourself:
  `python scripts/investigate_demo.py`.

## Limitations

- Supervisor is static routing, not an LLM deciding the next agent (the original spec's "decide
  which agent should act next" is only partly met; the real decision is after Review).
- One patch = one find-and-replace in one file; the shipped project has three bugs, so the demo
  pre-fixes two of them in a throwaway copy (printed by the demo).
- Retries return to `coding`, not `debugging`.
- Human approval is a function + CLI prompt, not yet an API/UI.
- Sandbox directories under `/tmp` are not cleaned up.
- `langsmith` is installed as a dependency of `langgraph` but is not configured or used.
- No token/cost tracking or structured event logging yet (planned for later phases).

## Things worth knowing about how this phase was built

- The build environment was reset mid-phase, wiping the uncommitted Phase 4 files. I restored the
  Phase 3 project from `AgentForge-phase3.zip`, re-created the Phase 4 files, and re-ran everything;
  the numbers above are from the restored project.
- One integration test initially failed because my scripted Gemini ran out of patches (the shipped
  project has three bugs, so one good patch can't pass). That was a test-setup error, not a graph
  bug; I fixed the test to supply enough patches.

## First commands to run (Phase 4)

```bash
pip install -e ".[dev]"
pytest -v                                   # 101 tests, no API key needed
python scripts/investigate_demo.py          # needs GEMINI_API_KEY in .env
```

---

# Phase 5

## Scope decision

The project never says "Phase 5" anywhere (checked: no file contains that string before this
phase). I inspected `README.md`, `BUILD_VERIFICATION.md`, and every source file per the request's
Step 1 and found the strongest documented signal in Phase 4's own "Limitations" section: *"Human
approval is a function call plus a CLI prompt in the demo. An API endpoint and UI for it come in
later phases."* Combined with the original spec's still-unbuilt Backend (FastAPI) and Database
sections, I scoped Phase 5 as: **a FastAPI backend + SQLite/Postgres persistence layer exposing
the Phase 4 multi-agent workflow as a real HTTP service.** I did not build a frontend, Docker,
an evaluation harness, or observability in this phase - none of those are named "Phase 5" in the
project either, and building all of them at once, at the same rigor as everything so far, is not
something I can do honestly in one pass. This is a scope judgment call, stated plainly rather than
silently narrowed - see README.md's Phase 5 section for the same explanation in context.

## What was built

- `app/db/database.py`, `models.py`, `repository.py` - SQLAlchemy persistence. The full
  `IncidentState` is stored as JSON in one column; a few columns are denormalized out of it for
  listing/sorting. SQLite by default (`DATABASE_URL`, default `sqlite:///./agentforge.db`).
- `app/api/schemas.py`, `deps.py`, `routes.py`, `app_factory.py` - 8 endpoints (create, investigate,
  list, get, evidence, patch, approve, report) plus `/health`.
- `app/main.py` - the real entrypoint (`uvicorn app.main:app`), builds real dependencies once at
  import time.
- `app/core/config.py` - added `database_url` setting.
- `.env.example` - activated `DATABASE_URL` and `GEMINI_EMBEDDING_MODEL` (the latter existed in
  code since Phase 3 but was missing from this file - fixed as part of Step 12's review).
- `.gitignore` - activated the `*.db` rule (was a commented-out placeholder).
- `pyproject.toml` - added `fastapi`, `uvicorn`, `sqlalchemy` to `dependencies`, `httpx` to `dev`
  (required by `fastapi.testclient.TestClient`).
- 17 new tests: `test_db_repository.py` (5), `test_api_incidents.py` (10), plus 2 added to
  `test_config.py` for the new setting.

## What was actually tested (real runs in this environment, right before packaging)

```
pytest backend/tests             -> 120 passed   (118 as of the API+DB work, +2 for the evaluation harness added after)
sample_project's own tests       -> 3 failed, 4 passed   (unchanged; git status clean)
```

Per-file counts (Phase 5 additions marked):

| File | Tests | |
|---|---|---|
| test_agentic_retrieval.py | 3 | Phase 3 |
| test_agents_unit.py | 14 | Phase 4 |
| **test_api_incidents.py** | **10** | **Phase 5** |
| test_chunking.py | 5 | Phase 3 |
| test_config.py | 8 | Phase 1 (6) + Phase 5 (2) |
| **test_db_repository.py** | **5** | **Phase 5** |
| test_demo_setup.py | 4 | Phase 4 |
| test_doc_tools.py | 5 | Phase 2 |
| test_embeddings.py | 5 | Phase 3 |
| test_gemini_client.py | 6 | Phase 1 |
| test_git_tools.py | 3 | Phase 2 |
| test_graph_integration.py | 7 | Phase 4 |
| test_incident_state.py | 5 | Phase 1 |
| test_ingest.py | 3 | Phase 3 |
| test_log_tools.py | 6 | Phase 2 |
| test_repo_tools.py | 8 | Phase 2 |
| test_retrieval.py | 1 | Phase 3 |
| test_test_tools.py | 3 | Phase 2 |
| test_vector_store.py | 6 | Phase 3 |
| test_workspace.py | 11 | Phase 4 |
| **Total** | **118** | 101 pre-existing + 17 new |

(`test_evaluation.py`'s 2 tests, added after this table was written for the Docker/evaluation
addendum below, bring the final total to 120 - see that section for the up-to-date number.)

`test_api_incidents.py` uses the REAL `create_app()`, a REAL in-memory SQLite database (via
`create_session_factory`), and a REAL sandboxed copy of `sample_project` (`tmp_path`-based, never
the shipped one) - only `GeminiClient` is a scripted fake (same pattern as Phase 4's
`test_graph_integration.py`). It genuinely proves, through the API rather than by calling Python
functions directly:

- **Full happy path**: create -> investigate -> poll to `awaiting_approval` -> read evidence/patch
  -> approve -> the real project file is genuinely modified on disk and its own tests would now
  pass -> the final report reflects `resolved`.
- **Rejection**: `approved: false` leaves the real project byte-identical and marks `failed`.
- **Retry through the API**: a bad-then-good scripted patch sequence reaches `awaiting_approval`
  with `retry_count: 1`, driven entirely through HTTP calls.
- **Conflict handling**: investigating twice, or approving before `awaiting_approval`, both return
  `409` rather than doing something silently wrong.
- **404s**: unknown incident id, and reading `/patch` before one exists.
- **Crash handling**: I intentionally made the scripted Gemini client raise `RuntimeError` mid-
  workflow and confirmed the incident is recorded as `failed` with the real error message in
  `messages` - not silently lost, not reported as a fake success. This directly satisfies the
  request's "do not hide failures" / "do not catch an exception and silently mark the workflow
  successful" requirement.
- **Background-task timing**: every test polls `GET /incidents/{id}` immediately after
  `POST /investigate` returns, with no sleep/retry loop, and the workflow has already completed by
  then. This confirms (empirically, not assumed) that Starlette's `TestClient` runs
  `BackgroundTasks` synchronously as part of the request/response cycle.
- I also confirmed `GET /openapi.json` returns `200` and lists all 8 documented endpoints, proving
  every response model (including `IncidentState` itself, returned directly from `GET
  /incidents/{id}`) is valid enough for FastAPI to generate a schema from - a real, if partial,
  check that the API's shape is self-consistent.

## What uses mocked/scripted Gemini

Identical pattern to Phase 4: a `MagicMock` whose `generate_structured` returns canned answers
based on which `response_model` was requested, and whose `embed_texts` returns a fixed vector.
Chroma, SQLite, the sandbox, patch application, FastAPI routing, and the LangGraph graph itself are
all real.

## What requires your real Gemini API key (NOT verified here)

- Everything already listed as unverified in Phase 4 (real patch quality, real root-cause/review
  reasoning, real embedding quality) - unchanged by this phase.
- **A real `uvicorn` server has never been started in this environment.** I verified `app/main.py`
  fails fast and clearly when `GEMINI_API_KEY` is unset (confirmed the exact `GeminiConfigError`
  message), which is the correct, documented behavior - but I have not run
  `uvicorn app.main:app` against a live key, and have not made a real `curl`/HTTP request against a
  running server. **Please run this yourself:**
  ```bash
  cd backend && uvicorn app.main:app --reload
  ```
  then use the `curl` sequence in README.md's Phase 5 section, or open `http://localhost:8000/docs`.

## Senior-engineer review pass (Step 12)

Checked and found clean:
- **Circular imports**: every module under `app/` (excluding `app.main`, which needs a real API key
  to import by design) imports successfully via `pkgutil.walk_packages` - 45 modules, no errors.
- **Hardcoded dev-machine paths**: none in `backend/`, `scripts/`, or `sample_project/`.
- **Hardcoded secrets/API keys**: none found (pattern-searched for Google/OpenAI-shaped key strings).
- **Bare `except:`**: none anywhere in the project; broad catches are all `except Exception as exc`
  paired with recording the real error (e.g. `_run_investigation`'s crash handling), never a silent
  swallow.
- **Leftover TODO/FIXME/XXX**: none (one false-positive grep hit on the literal text "xxxx" inside
  a docstring's example path).

Found and fixed:
- `.env.example` was missing `GEMINI_EMBEDDING_MODEL` (in code since Phase 3, never added here) and
  still listed a `VECTOR_DB_PATH` placeholder that was never actually used (Chroma is in-memory) -
  removed the stale placeholder, added the real, missing variable.
- `.gitignore`'s `*.db` rule was commented out as a "later phase" placeholder; activated it now that
  Phase 5 creates a real SQLite file.

## Known, named limitations

- `_WORKSPACES` (incident id -> sandbox path) is an in-process Python dict, not persisted. A server
  restart loses track of any in-flight sandbox; that incident would need to be re-investigated
  (a fresh sandbox would be created). This is fine for a single-process learning deployment and
  wrong for anything running multiple workers - named here rather than hidden.
- No authentication on any endpoint.
- No DB migrations (`create_all()` only) - fine for two small tables and no schema history need yet.
- No frontend, Docker, evaluation harness, or observability (see "Scope decision" above).
- Everything already named as a limitation in Phase 4 that Phase 5 didn't touch still applies
  (static supervisor routing, one-file-per-patch, retries return to `coding` not `debugging`,
  `/tmp` sandbox dirs aren't cleaned up, `langsmith` installed but unused).

## Phase 5 addendum: Docker and the evaluation harness

After the API+DB work above (and the "Scope decision" that explicitly deferred these), the
following user message asked for the rest of the original spec's still-open items in the same
pass. I added two of them for real; the rest I judged couldn't be done at the same rigor as
everything else in the time available, and said so rather than faking them - see README.md's
"What's still not built" section for the complete, current list.

**Docker** - `Dockerfile`, `docker-compose.yml`, `.dockerignore`. Single service, SQLite on a
named volume, no Postgres container by default (matches the documented SQLite default; adding an
unused Postgres service would be exactly the unnecessary infrastructure the project avoids).
**Not build-tested**: this environment has no Docker daemon (`docker: not found`). I reviewed the
Dockerfile by hand for correctness (paths, the two-step dependency-then-source copy for layer
caching, `PYTHONPATH`, `EXPOSE 8000`, the `uvicorn app.main:app` command matching `app/main.py`'s
actual module path) but did not run `docker build` or `docker compose up`. Run `docker compose up
--build` yourself to verify.

**Evaluation harness** (`evaluation/run_evaluation.py`) - genuinely run, not just written. It
reuses `scripts/investigate_demo.py`'s incident definitions and bug-isolation logic (imported, not
duplicated) to run the full graph against each of `sample_project`'s 3 real bugs, scoring: did the
patch target the correct file, did the sandbox test suite end up fully passing, how many retries,
how long it took. Evaluates 3 incidents, not the spec's suggested "10-20" - `sample_project` has
exactly 3 real, distinct bugs, and inventing more incidents with no corresponding real bug would
produce benchmark-shaped numbers that mean nothing, which this project's own rules explicitly
forbid. With no `GEMINI_API_KEY` (the case in this environment) it runs with a scripted Gemini
client and labels every result `mock`.

Real output from running it in this environment (no API key -> mock mode), saved at
`evaluation/results/mock_run.json`:

```
incident       mode  status             file ok  tests ok  retries  seconds
login          mock  awaiting_approval  True     True      0        1.03
orders-total   mock  awaiting_approval  True     True      0        0.91
orders-404     mock  awaiting_approval  True     True      0        0.88

3/3 reached awaiting_approval or resolved
3/3 proposed a patch targeting the correct file
3/3 ended with the sandbox test suite fully passing
0 total retries used across all 3 incidents
```

**A real bug found and fixed while building this**: the first version of the harness's scripted
`embed_texts` returned exactly one embedding vector regardless of how many texts were passed in,
so ingesting the knowledge base's 16 chunks failed with `Got 16 chunks but 1 embeddings` on every
single incident (all 3 showed `status: error`). Root cause: `return_value=[[1.0, 0.0]]` (a fixed
return) instead of a function of the input length. Fixed by making it `side_effect=lambda texts,
...: [[1.0, 0.0] for _ in texts]`, re-ran, and got the real, correct output above. Left in this
document rather than quietly fixed and unmentioned, per this phase's explicit "don't hide
failures" instruction.

**2 new tests** in `test_evaluation.py`, run as part of the 120 above: that the scripted client's
patch always targets the right file, and that `run_one` resolves all 3 real incidents in mock mode
with no error.

## Fresh-environment verification (Step 16)

Unzipped the packaged `AgentForge-phase5.zip` into a clean directory (`/tmp/verify_phase5`,
separate from the working directory everything above was built in), installed dependencies there,
and re-ran the full suite against the extracted copy - not the working directory:

```
pytest backend/tests        -> 120 passed
sample_project's own tests  -> 3 failed, 4 passed
git status (sample_project) -> clean
```

Also confirmed directly against the zip's file listing (not the working directory): 0 entries
matching `__pycache__`, `.pyc`, `.pytest_cache`, or `.env` are inside the archive, and
`sample_project/.git/` is present and intact (needed for `git_tools` to work immediately after
extraction).

## First commands to run (Phase 5)

```bash
pip install -e ".[dev]"
pytest -v                                    # 120 tests, no API key needed

# Real server, with your own Gemini key in .env:
cd backend && uvicorn app.main:app --reload
# Interactive docs: http://localhost:8000/docs
```

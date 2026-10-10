# Resume project summary

Measurable claims only where this project's own tests/evaluation actually
measured them. No "100% autonomous", no "AGI", no "zero hallucinations",
no "enterprise-grade" - see `BUILD_VERIFICATION.md` for what backs every
number below.

## Option 1 (concise)

> Built AgentForge, a multi-agent AI incident-investigation system
> (Python, LangGraph, Gemini, FastAPI, React) that diagnoses software
> bugs from logs/code/docs, proposes and sandbox-tests a fix, and applies
> it only after a human approval step. 131 automated tests, including
> full LangGraph routing/retry/safety integration tests.

## Option 2 (architecture-forward)

> Designed and implemented a 7-agent LangGraph workflow (investigation,
> RAG-grounded diagnosis, patch generation, sandboxed testing, automated
> review, human approval) backed by a FastAPI + SQLite API and a React
> frontend. Every destructive action is sandboxed and gated behind an
> explicit human-approval function - verified by tests that assert the
> real project is byte-identical until approval is given.

## Option 3 (RAG/agentic-AI-forward)

> Implemented agentic RAG (Gemini decides what to retrieve, evaluates
> whether it's sufficient, retries with feedback) over a project
> knowledge base, feeding a multi-agent incident-diagnosis pipeline with
> a bounded reflection/retry loop. Built an evaluation harness measuring
> root-cause-targeting accuracy and fix-verification pass rate against
> the project's real, intentional bugs - not synthetic benchmarks.

## What to say if asked for numbers

"131 tests pass, covering every agent individually and the compiled
LangGraph workflow end to end, including the retry path and the
human-approval safety boundary. I have not yet run this against a live
Gemini API key in my own development environment - every test uses a
scripted Gemini client that returns realistic structured responses, which
verifies the system's logic and safety, not Gemini's actual output
quality." That sentence is more credible in an interview than a vague
"it works great" - and it's true.

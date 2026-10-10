# The multi-agent workflow

## Agents

| Agent | File | Uses Gemini? | What it does |
|---|---|---|---|
| Supervisor | `backend/app/agents/supervisor.py` | No | Marks the incident `in_progress`. Static routing - the workflow is linear enough that an LLM deciding "what's next" would add cost and non-determinism without benefit; the one real routing decision in this graph happens after Review. |
| Investigation | `backend/app/agents/investigation.py` | 1 call | Reads `logs/app.log` and greps the sandbox source (`app/tools/log_tools.py`, `repo_tools.py` - deterministic), then one Gemini call summarizes the raw evidence into key findings. |
| Knowledge/RAG | `backend/app/agents/knowledge.py` | 0-2 calls | Agentic retrieval over `knowledge_base/` by default (decide what to search -> retrieve -> judge sufficiency -> retry if needed, up to 2 rounds - `backend/app/rag/agentic_retrieval.py`), falling back to free keyword search on a Gemini failure. See `docs/rag.md`. |
| Debugging | `backend/app/agents/debugging.py` | 1 call | One structured `RootCauseAnalysis`: a root cause, a confidence score, and which specific evidence supports it - never a bare conclusion. |
| Coding | `backend/app/agents/coding.py` | 1 call | One structured `PatchProposal` (find-and-replace on one file), applied **only** to the sandbox workspace. On a retry, the previous attempt's test/review feedback is folded into the prompt (reflection). |
| Testing | `backend/app/agents/testing.py` | No | Runs the sandbox's real `pytest` suite (`app/tools/test_tools.py`). A patch's stated explanation is never treated as evidence it works - the actual test exit code is. |
| Review/Security | `backend/app/agents/review.py` | 1 call | Reviews the **actual diff** (not the Coding Agent's explanation) plus the real test results; can reject a technically-passing fix for being risky or out of scope. |
| Human Approval | `backend/app/agents/human_approval.py` | No | Not a graph node. `apply_human_decision()` is the only function allowed to copy a fix into the real project, and only when called with `approved=True`. |

## The graph

```
START -> supervisor -> investigation -> knowledge -> debugging -> coding -> testing -> review
                                                                     ^                     |
                                                                     |  route_after_review  |
                                                                     +------ retry <--------+
                                                   approve -> awaiting_approval -> END
                                                   fail (retries exhausted) -> failed -> END
```

`route_after_review` (`backend/app/graph/workflow.py`) only reads state and
returns a routing key - `"approve"`, `"retry"`, or `"fail"`. `retry_count`
is incremented inside the Coding Agent itself (when it sees a `test_result`
already on the state, meaning this is a second attempt), not in the router.
`MAX_RETRIES = 2`, so the Coding Agent runs at most 3 times total.

## Reflection

On a retry, `coding.py` builds a feedback string from the previous
`test_result.summary` and `review_result.concerns`/`reasoning`, and
prepends "A previous fix attempt did not work: ..." to the prompt. The
sandbox also keeps the earlier edits rather than resetting, so a retry
builds on what's already there.

## Structured outputs

Every Gemini call that needs reliable, parseable data uses
`GeminiClient.generate_structured()` (`backend/app/llm/gemini.py`) with a
Pydantic model as the schema (`backend/app/models/agent_outputs.py`):
`EvidenceSummary`, `RootCauseAnalysis`, `PatchProposal`, `ReviewResult`.
Gemini returns JSON matching the schema; Pydantic validates it. A
malformed response raises a normal `ValidationError` rather than silently
producing bad data.

## Why a one-file find-and-replace patch, not a full diff/PR

`PatchProposal` is deliberately simple: `target_file`,
`original_snippet`, `replacement_snippet`. It's easy for Gemini to produce
reliably, easy to validate (the snippet must match the file exactly once
or the patch is rejected - `backend/app/agents/workspace.py`'s
`apply_patch`), and easy for a human to read in the "Proposed fix" UI
section. The real tradeoff: one patch fixes one bug in one file. Since
`sample_project` has three distinct, unrelated bugs, one investigation run
fixes one of them - see `docs/rag.md`'s sibling file
`sample-project-bugs.md` and the evaluation harness (`evaluation/`), which
evaluates exactly those three.

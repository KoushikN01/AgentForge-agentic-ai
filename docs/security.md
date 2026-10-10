# Security

## Threat model

AgentForge lets an LLM propose and (in a sandbox) apply code changes.
The real risk isn't "the LLM is malicious" - it's "the LLM is wrong,"
and the system has to stay safe even when it is. Every control below
exists for that reason, not to defend against an adversarial Gemini.

## Controls, and where to find them

| Control | Where | What it prevents |
|---|---|---|
| Sandbox-only patching | `app/agents/workspace.py` (`create_incident_workspace`, `apply_patch`) | An agent editing the real `sample_project/` directly. Every patch targets a throwaway temp-directory copy. |
| Path traversal guard | `app/tools/security.py` (`resolve_within_root`), used by every file-touching tool and `workspace.py` | A patch or tool call escaping its allowed root, e.g. `target_file: "../../etc/passwd"`. |
| Patch validation | `workspace.apply_patch` | A stale or ambiguous patch applying to the wrong place - `original_snippet` must match the file exactly once, or it's rejected outright (not a best-effort replace). |
| Allowlisted test execution | `app/tools/test_tools.py` | Arbitrary shell/code execution. The only command ever run is `python -m pytest <path-inside-the-project-root>` - no shell string construction, no user-controlled command. |
| Allowlisted git operations | `app/tools/git_tools.py` | Same pattern - only `git diff`/`git status`-class read-only subcommands, never a general shell call. |
| Bounded retries | `app/graph/workflow.py` (`MAX_RETRIES = 2`) | An infinite agent loop. The Coding Agent runs at most 3 times total. |
| Deterministic testing | `app/agents/testing.py` | "The LLM says it works" standing in for "it actually passed." Tests are executed, not asked about. |
| Separate Review step | `app/agents/review.py` | A technically-passing patch that's still risky or out-of-scope reaching approval unreviewed. |
| Human approval gate | `app/agents/human_approval.py` (`apply_human_decision`) | Automatic application of any change to the real project. This is the **only** function in the codebase allowed to write to `sample_project/`, and only when called with `approved=True`. Not a graph node - a human (or, in the API, a `POST /approve` call) must invoke it explicitly. |
| Frontend never bypasses this | `frontend/src/components/IncidentDetail.jsx` | The approve/reject buttons only render when the backend reports `status === "awaiting_approval"`, and both call `POST /incidents/{id}/approve` - the same endpoint and the same `apply_human_decision` path the backend's own tests exercise. The frontend has no code path that touches the filesystem directly. |

## Secrets

- `GEMINI_API_KEY` is read from an environment variable
  (`app/core/config.py`), never hard-coded, never logged (`app/llm/gemini.py`
  never includes it in a log line).
- `.env` is gitignored and never packaged (verified below).
- `.env.example` contains placeholder values only.

## What's genuinely NOT done

- **No authentication or authorization** on any API endpoint. Anyone who
  can reach the API can create incidents, start investigations, and
  approve/reject fixes. This is a real, deliberately-undone item: adding
  auth (API keys, OAuth, whatever) is a legitimate production-hardening
  task, not part of this learning project's intended scope, and adding it
  half-heartedly (e.g. a single shared hardcoded token) would be worse
  than being explicit that it's absent.
- **No rate limiting** on Gemini-calling endpoints - a client could spam
  `POST /investigate` and run up API costs.
- **No sandboxing below the OS level** (no container/VM per investigation)
  - the sandbox is a plain temp directory with path-traversal guards, not
    a hardened execution environment. Fine for a learning project running
    locally; not what you'd want multi-tenant in production.

## Verification performed for this audit

```bash
grep -rn "api_key\|API_KEY\|secret\|password" backend/app frontend/src --include=*.py --include=*.jsx --include=*.js
# only config.py reading os.environ, and auth.py's *documentation* of the bug it has - no literal secret values
find . -name ".env" -not -path "*/node_modules/*"
# no output - no .env file exists in the project tree
unzip -l <packaged zip> | grep -E "\.env$|\.db$"
# no output - confirmed again at packaging time, see BUILD_VERIFICATION.md
```

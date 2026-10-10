# Knowledge Base

Plain markdown documents that `app/tools/doc_tools.py` searches over.

```
knowledge_base/
├── architecture.md          # how sample_project is put together
├── api_documentation.md     # what each endpoint should do
├── deployment_notes.md      # required env vars, deploy checklist
├── troubleshooting_guide.md # known symptom -> likely cause patterns
└── incidents/
    └── INC-2026-01-login-500.md   # a previously resolved incident
```

## Why it's organized as flat markdown files

Phase 2's `doc_tools.search_docs()` does plain keyword search across these
files. Phase 3 will add a real RAG pipeline (chunk → embed → vector store
→ semantic retrieval) over this same folder. Keeping the knowledge base as
plain, well-organized markdown now means Phase 3 only has to change *how*
these files are searched, not restructure what's in them or how agents
call `search_docs()`.

## Adding new documents

Add a new `.md` file anywhere under this folder (a new file directly here,
or a new file under `incidents/` for a past incident write-up) and it will
automatically be picked up by `list_documents()` / `search_docs()` — no
registration needed.

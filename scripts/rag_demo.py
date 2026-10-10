"""
Demo script: ingest knowledge_base/ and run agentic retrieval against a
real Gemini API for one sample incident.

Requires a real GEMINI_API_KEY in your .env file — this script makes
real, billed (though very cheap) calls to Gemini and has NOT been run in
the environment this project was built in, since no API key was
available there. See BUILD_VERIFICATION.md.

Usage (from the project root, with your virtualenv active):
    python scripts/rag_demo.py
"""

import sys
from pathlib import Path

# Let this script be run directly with `python scripts/rag_demo.py`
# without needing the project installed as a package first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.llm.gemini import GeminiClient, GeminiConfigError  # noqa: E402
from app.rag.agentic_retrieval import agentic_retrieve  # noqa: E402
from app.rag.ingest import ingest_knowledge_base  # noqa: E402

SAMPLE_INCIDENT = "POST /api/auth/login is returning HTTP 500 after yesterday's deployment."


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    knowledge_base = project_root / "knowledge_base"

    try:
        client = GeminiClient()
    except GeminiConfigError as exc:
        print(f"Can't run the demo: {exc}")
        return

    print(f"Ingesting {knowledge_base} ...")
    collection = ingest_knowledge_base(knowledge_base, client)
    print(f"Stored {collection.count()} chunks in the vector store.\n")

    print(f"Incident: {SAMPLE_INCIDENT}\n")
    result = agentic_retrieve(client, collection, SAMPLE_INCIDENT)

    for round_ in result.rounds:
        print(f"--- Round {round_.round_number} ---")
        print(f"Searched for: {round_.plan.queries}  ({round_.plan.reasoning})")
        for chunk in round_.retrieved:
            print(f"  found: {chunk.chunk.source_path} (distance={chunk.distance:.3f})")
        print(f"Sufficient? {round_.sufficiency.is_sufficient} — {round_.sufficiency.reasoning}")
        print()

    print(f"Stopped because sufficient: {result.stopped_because_sufficient}")
    print(f"Final evidence from: {[c.chunk.source_path for c in result.final_chunks]}")


if __name__ == "__main__":
    main()

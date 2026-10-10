"""
Shared data types for the RAG pipeline.

Kept separate from app.tools.models because these describe RAG-specific
concepts (chunks, retrieval scores, agentic retrieval rounds) rather than
general tool outputs.
"""

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """One piece of a document, small enough to embed and retrieve individually."""

    id: str  # stable id, e.g. "runbook.md::0"
    source_path: str  # which knowledge_base file this came from
    chunk_index: int  # position of this chunk within its source document
    text: str


class RetrievedChunk(BaseModel):
    """A chunk returned by a similarity search, with how close the match was."""

    chunk: Chunk
    distance: float  # lower = more similar (Chroma's default: squared L2 distance)


class RetrievalPlan(BaseModel):
    """
    What the Knowledge/RAG agent decided it needs to search for.

    This is the "decide what information is needed" step of agentic RAG —
    Gemini reads the incident description and proposes search queries,
    rather than the incident text itself being used as the query verbatim.
    """

    queries: list[str] = Field(description="1-3 short search queries to run against the knowledge base")
    reasoning: str = Field(description="One sentence on why these queries were chosen")


class SufficiencyCheck(BaseModel):
    """
    Whether the retrieved context is enough to explain the incident, or
    whether another round of retrieval is needed. This is the "evaluate
    evidence, retrieve again if necessary" step of agentic RAG.
    """

    is_sufficient: bool
    reasoning: str
    missing_information: str | None = Field(
        default=None, description="What's still missing, if not sufficient"
    )


class RetrievalRound(BaseModel):
    """One iteration of the agentic retrieval loop, kept for observability."""

    round_number: int
    plan: RetrievalPlan
    retrieved: list[RetrievedChunk]
    sufficiency: SufficiencyCheck


class AgenticRetrievalResult(BaseModel):
    """The full outcome of running agentic retrieval for one incident."""

    rounds: list[RetrievalRound]
    final_chunks: list[RetrievedChunk]

    @property
    def stopped_because_sufficient(self) -> bool:
        return bool(self.rounds) and self.rounds[-1].sufficiency.is_sufficient

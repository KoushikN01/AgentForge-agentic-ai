"""
Splits a document's text into smaller chunks for embedding and retrieval.

This is plain, deterministic Python — no LLM call. Splitting on blank
lines (paragraphs) keeps each chunk on a natural boundary instead of
cutting mid-sentence, which matters for embedding quality: a chunk should
be a coherent unit of meaning, not an arbitrary character slice.
"""

from app.rag.models import Chunk

# Most of our knowledge_base documents are short (a few hundred words), so
# a fairly generous chunk size keeps most documents in one or two chunks
# rather than fragmenting them unnecessarily.
_DEFAULT_MAX_CHARS = 600


def chunk_text(text: str, source_path: str, max_chars: int = _DEFAULT_MAX_CHARS) -> list[Chunk]:
    """
    Split `text` into Chunk objects, grouping consecutive paragraphs
    together as long as the running chunk stays under `max_chars`. A
    single paragraph longer than max_chars becomes its own chunk rather
    than being cut off (we never truncate content).
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[Chunk] = []
    current_paragraphs: list[str] = []
    current_length = 0

    def flush() -> None:
        if not current_paragraphs:
            return
        chunk_text_value = "\n\n".join(current_paragraphs)
        chunks.append(
            Chunk(
                id=f"{source_path}::{len(chunks)}",
                source_path=source_path,
                chunk_index=len(chunks),
                text=chunk_text_value,
            )
        )

    for paragraph in paragraphs:
        if current_paragraphs and current_length + len(paragraph) > max_chars:
            flush()
            current_paragraphs = []
            current_length = 0

        current_paragraphs.append(paragraph)
        current_length += len(paragraph)

    flush()  # don't forget whatever's left after the loop
    return chunks

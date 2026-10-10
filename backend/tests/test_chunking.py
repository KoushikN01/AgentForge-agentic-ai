from app.rag.chunking import chunk_text


def test_short_document_becomes_one_chunk():
    text = "# Title\n\nJust one short paragraph here."

    chunks = chunk_text(text, source_path="doc.md")

    assert len(chunks) == 1
    assert chunks[0].id == "doc.md::0"
    assert chunks[0].source_path == "doc.md"
    assert chunks[0].chunk_index == 0
    assert "one short paragraph" in chunks[0].text


def test_long_document_splits_into_multiple_chunks():
    # Three paragraphs, each bigger than max_chars=50, so each should
    # become its own chunk.
    paragraphs = ["A" * 60, "B" * 60, "C" * 60]
    text = "\n\n".join(paragraphs)

    chunks = chunk_text(text, source_path="doc.md", max_chars=50)

    assert len(chunks) == 3
    assert chunks[0].text == "A" * 60
    assert chunks[1].text == "B" * 60
    assert chunks[2].text == "C" * 60
    assert [c.chunk_index for c in chunks] == [0, 1, 2]


def test_short_paragraphs_are_grouped_into_one_chunk():
    text = "One.\n\nTwo.\n\nThree."

    chunks = chunk_text(text, source_path="doc.md", max_chars=1000)

    assert len(chunks) == 1
    assert "One." in chunks[0].text
    assert "Two." in chunks[0].text
    assert "Three." in chunks[0].text


def test_blank_document_produces_no_chunks():
    chunks = chunk_text("\n\n   \n\n", source_path="empty.md")

    assert chunks == []


def test_chunk_ids_are_unique_and_ordered():
    text = "\n\n".join(["X" * 60] * 4)

    chunks = chunk_text(text, source_path="doc.md", max_chars=50)

    assert [c.id for c in chunks] == ["doc.md::0", "doc.md::1", "doc.md::2", "doc.md::3"]

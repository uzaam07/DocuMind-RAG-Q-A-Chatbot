from __future__ import annotations

import pytest

from app.services.chunking import chunk_blocks, split_text
from app.services.parsing import Block

LONG = " ".join(f"Sentence number {i} talks about topic {i % 7}." for i in range(120))


def test_short_text_is_one_chunk() -> None:
    assert split_text("hello world", 800, 150) == ["hello world"]


def test_chunks_respect_size() -> None:
    chunks = split_text(LONG, 400, 80)
    assert len(chunks) > 5
    assert all(len(c) <= 400 for c in chunks)


def test_chunks_overlap() -> None:
    chunks = split_text(LONG, 400, 100)
    for a, b in zip(chunks, chunks[1:], strict=False):
        last_sentence = a[a.rfind("Sentence") :]
        assert last_sentence in b, (a[-80:], b[:80])


def test_all_text_is_covered() -> None:
    chunks = split_text(LONG, 300, 60)
    joined = " ".join(chunks)
    for i in (0, 57, 119):
        assert f"Sentence number {i} " in joined


def test_prefers_paragraph_boundaries() -> None:
    text = ("a" * 300 + "\n\n") + ("b" * 300 + "\n\n") + ("c" * 300)
    chunks = split_text(text, 650, 0)
    assert chunks[0].startswith("a") and "b" in chunks[0] and "c" not in chunks[0]


def test_unbroken_text_is_hard_split() -> None:
    chunks = split_text("x" * 2500, 800, 100)
    assert all(len(c) <= 800 for c in chunks) and sum(len(c) for c in chunks) >= 2500


def test_invalid_size() -> None:
    with pytest.raises(ValueError):
        split_text("abc", 0, 0)


def test_labels_and_page_tracking() -> None:
    blocks = [
        Block(LONG, page=1),
        Block("Short page two.", page=2),
        Block("Body of a section.", section="Leave Policy"),
        Block("Orphan text with no heading."),
    ]
    chunks = chunk_blocks(blocks, 400, 80)
    pages = [c for c in chunks if c.page is not None]
    assert {c.page for c in pages} == {1, 2}
    assert all(c.label == f"Page {c.page}" for c in pages)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    page_two = [c for c in chunks if c.page == 2]
    assert len(page_two) == 1 and page_two[0].text == "Short page two."
    assert any(c.label == "Section: Leave Policy" for c in chunks)
    assert chunks[-1].label == f"Chunk {len(chunks)}"

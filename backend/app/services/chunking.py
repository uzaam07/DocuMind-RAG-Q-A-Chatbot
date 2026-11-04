"""Recursive text splitter with overlap, producing labelled chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.parsing import Block

_SPLITTERS = (
    lambda t: re.split(r"(?<=\n\n)", t),
    lambda t: t.splitlines(keepends=True),
    lambda t: re.split(r"(?<=[.!?]\s)", t),
    lambda t: re.split(r"(?<=\s)", t),
)


@dataclass
class Chunk:
    """One embeddable passage with its location metadata."""

    text: str
    chunk_index: int
    page: int | None
    section: str | None
    label: str


def _pieces(text: str, size: int, level: int = 0) -> list[str]:
    if len(text) <= size:
        return [text]
    if level >= len(_SPLITTERS):
        return [text[i : i + size] for i in range(0, len(text), size)]
    parts = [p for p in _SPLITTERS[level](text) if p]
    if len(parts) <= 1:
        return _pieces(text, size, level + 1)
    out: list[str] = []
    for part in parts:
        out.extend(_pieces(part, size, level + 1) if len(part) > size else [part])
    return out


def split_text(text: str, size: int = 800, overlap: int = 150) -> list[str]:
    """Split on paragraphs, then lines, sentences and words, keeping ~overlap chars of context."""
    if size <= 0:
        raise ValueError("size must be positive")
    overlap = max(0, min(overlap, size // 2))
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for piece in _pieces(text, size):
        if current and current_len + len(piece) > size:
            chunks.append("".join(current).strip())
            keep: list[str] = []
            kept = 0
            for prev in reversed(current):
                if kept + len(prev) > overlap:
                    break
                keep.insert(0, prev)
                kept += len(prev)
            if kept + len(piece) > size:
                keep, kept = [], 0
            current, current_len = keep, kept
        current.append(piece)
        current_len += len(piece)
    if current:
        chunks.append("".join(current).strip())
    return [c for c in chunks if c]


def chunk_blocks(blocks: list[Block], size: int, overlap: int) -> list[Chunk]:
    """Chunk each block separately so chunks never cross a page or section boundary."""
    chunks: list[Chunk] = []
    for block in blocks:
        for text in split_text(block.text, size, overlap):
            index = len(chunks)
            if block.page is not None:
                label = f"Page {block.page}"
            elif block.section:
                label = f"Section: {block.section}"
            else:
                label = f"Chunk {index + 1}"
            chunks.append(Chunk(text, index, block.page, block.section, label))
    return chunks

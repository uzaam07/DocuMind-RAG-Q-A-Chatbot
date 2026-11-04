"""Per-user in-memory BM25 index, rebuilt lazily after invalidation."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from app.services import vectorstore
from app.services.textutil import tokenize
from app.services.vectorstore import Hit


@dataclass
class _Index:
    bm25: BM25Okapi
    hits: list[Hit]
    token_sets: list[set[str]]


_lock = threading.Lock()
_indexes: dict[str, _Index] = {}


def invalidate(user_id: str) -> None:
    """Forget a user's index; it is rebuilt on next search."""
    with _lock:
        _indexes.pop(user_id, None)


def clear() -> None:
    with _lock:
        _indexes.clear()


def _build(user_id: str) -> _Index | None:
    hits = vectorstore.all_chunks(user_id)
    if not hits:
        return None
    corpus = [tokenize(h.text) or ["_"] for h in hits]
    return _Index(BM25Okapi(corpus), hits, [set(c) for c in corpus])


def search(user_id: str, query: str, n: int, doc_ids: list[str] | None = None) -> list[Hit]:
    """Top-n chunks by BM25 that share at least one term with the query."""
    with _lock:
        index = _indexes.get(user_id)
        if index is None:
            index = _build(user_id)
            if index is None:
                return []
            _indexes[user_id] = index
    terms = tokenize(query)
    if not terms:
        return []
    scores = index.bm25.get_scores(terms)
    allowed = set(doc_ids) if doc_ids else None
    ranked: list[tuple[float, int]] = []
    qset = set(terms)
    for i, hit in enumerate(index.hits):
        if allowed is not None and hit.doc_id not in allowed:
            continue
        if qset & index.token_sets[i]:
            ranked.append((float(scores[i]), i))
    ranked.sort(key=lambda r: (-r[0], r[1]))
    return [
        Hit(
            id=index.hits[i].id,
            doc_id=index.hits[i].doc_id,
            filename=index.hits[i].filename,
            label=index.hits[i].label,
            text=index.hits[i].text,
            chunk_index=index.hits[i].chunk_index,
            score=score,
        )
        for score, i in ranked[:n]
    ]

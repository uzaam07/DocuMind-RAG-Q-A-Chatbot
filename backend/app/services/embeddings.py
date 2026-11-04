"""Batched, cached embeddings."""

from __future__ import annotations

import hashlib
from collections.abc import Callable

import numpy as np
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import EmbeddingCacheEntry
from app.services.cache import embedding_stats
from app.services.llm import LLMClient

_IN_CHUNK = 500


def embedding_key(model: str, text: str) -> str:
    return hashlib.sha256(f"{model}\x00{text}".encode()).hexdigest()


def embed_texts(
    db: Session,
    llm: LLMClient,
    texts: list[str],
    *,
    batch_size: int = 64,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[list[float]]:
    """Embed texts, reusing cached vectors and batching the rest into provider calls."""
    if not texts:
        return []
    keys = [embedding_key(llm.embedding_model, t) for t in texts]
    unique = list(dict.fromkeys(keys))
    cached: dict[str, list[float]] = {}
    for i in range(0, len(unique), _IN_CHUNK):
        part = unique[i : i + _IN_CHUNK]
        rows = db.execute(
            select(EmbeddingCacheEntry.key, EmbeddingCacheEntry.vector).where(
                EmbeddingCacheEntry.key.in_(part)
            )
        ).all()
        for key, blob in rows:
            cached[key] = np.frombuffer(blob, dtype=np.float32).tolist()
    embedding_stats.hit(sum(1 for k in keys if k in cached))
    missing_text: dict[str, str] = {}
    for key, text in zip(keys, texts, strict=True):
        if key not in cached and key not in missing_text:
            missing_text[key] = text
    embedding_stats.miss(sum(1 for k in keys if k not in cached))

    total = len(unique)
    done = total - len(missing_text)
    if on_progress:
        on_progress(done, total)
    pending = list(missing_text.items())
    for i in range(0, len(pending), batch_size):
        batch = pending[i : i + batch_size]
        vectors = llm.embed([text for _, text in batch])
        rows = []
        for (key, _), vec in zip(batch, vectors, strict=True):
            cached[key] = vec
            rows.append({"key": key, "vector": np.asarray(vec, dtype=np.float32).tobytes()})
        db.execute(sqlite_insert(EmbeddingCacheEntry).on_conflict_do_nothing(), rows)
        db.commit()
        done += len(batch)
        if on_progress:
            on_progress(done, total)
    return [cached[k] for k in keys]

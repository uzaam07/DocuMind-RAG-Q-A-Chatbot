"""Answer cache (SQLite, TTL) and hit/miss counters shared with the embedding cache."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import AnswerCacheEntry, EmbeddingCacheEntry, utcnow


class CacheStats:
    """Thread-safe hit/miss counters."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def hit(self, n: int = 1) -> None:
        with self._lock:
            self.hits += n

    def miss(self, n: int = 1) -> None:
        with self._lock:
            self.misses += n

    def snapshot(self) -> dict[str, float | int]:
        with self._lock:
            total = self.hits + self.misses
            rate = round(self.hits / total, 4) if total else 0.0
            return {"hits": self.hits, "misses": self.misses, "hit_rate": rate}

    def reset(self) -> None:
        with self._lock:
            self.hits = 0
            self.misses = 0


answer_stats = CacheStats()
embedding_stats = CacheStats()


def reset_counters() -> None:
    answer_stats.reset()
    embedding_stats.reset()


def answer_key(
    *,
    user_id: str,
    question: str,
    doc_ids: list[str],
    index_version: int,
    mode: str,
    chat_model: str,
    embedding_model: str,
    top_k: int,
    history_digest: str,
) -> str:
    """Stable hash of everything that can change an answer."""
    payload = [
        user_id,
        question,
        sorted(doc_ids),
        index_version,
        mode,
        chat_model,
        embedding_model,
        top_k,
        history_digest,
    ]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def get_answer(db: Session, key: str) -> dict | None:
    """Return a cached payload or None; expired rows are deleted. Updates hit/miss counters."""
    row = db.get(AnswerCacheEntry, key)
    if row is not None and row.expires_at <= utcnow():
        db.delete(row)
        db.commit()
        row = None
    if row is None:
        answer_stats.miss()
        return None
    answer_stats.hit()
    return json.loads(row.payload_json)


def put_answer(db: Session, key: str, user_id: str, payload: dict, ttl_seconds: int) -> None:
    """Store a payload with a time-to-live."""
    now = utcnow()
    entry = AnswerCacheEntry(
        key=key,
        user_id=user_id,
        payload_json=json.dumps(payload, ensure_ascii=False),
        created_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    db.merge(entry)
    db.commit()


def purge_user_answers(db: Session, user_id: str) -> None:
    """Drop all cached answers for a user (called when their index changes)."""
    db.execute(delete(AnswerCacheEntry).where(AnswerCacheEntry.user_id == user_id))
    db.commit()


def count_answers(db: Session, user_id: str) -> int:
    stmt = (
        select(func.count())
        .select_from(AnswerCacheEntry)
        .where(AnswerCacheEntry.user_id == user_id, AnswerCacheEntry.expires_at > utcnow())
    )
    return int(db.scalar(stmt) or 0)


def count_embeddings(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(EmbeddingCacheEntry)) or 0)

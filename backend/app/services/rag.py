"""RAG orchestration: cache lookup, follow-up rewrite, retrieval, grounded answer, fallback."""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Document, User
from app.services import cache, retrieval
from app.services.embeddings import embed_texts
from app.services.llm import (
    NOT_FOUND_MESSAGE,
    NOT_FOUND_SENTINEL,
    ContextPassage,
    get_llm,
)
from app.services.textutil import best_sentence, normalize_question
from app.services.vectorstore import Hit

Event = dict  # {"event": str, "data": dict}


def _ev(name: str, data: dict) -> Event:
    return {"event": name, "data": data}


def _citation(i: int, hit: Hit, question: str) -> dict:
    return {
        "id": i,
        "doc_id": hit.doc_id,
        "filename": hit.filename,
        "page_or_section": hit.label,
        "snippet": hit.text,
        "highlight": best_sentence(question, hit.text),
        "score": round(float(hit.score), 4),
    }


def _replay_chunks(text: str) -> Iterator[str]:
    words = re.findall(r"\S+\s*", text)
    for i in range(0, len(words), 4):
        yield "".join(words[i : i + 4])


def _history_digest(history: list[tuple[str, str]]) -> str:
    if not history:
        return ""
    return hashlib.sha256(json.dumps(history[-6:], ensure_ascii=False).encode()).hexdigest()[:16]


def _ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def answer_events(
    db: Session,
    user: User,
    question: str,
    doc_ids: list[str] | None,
    mode: str | None,
    history: list[tuple[str, str]] | None = None,
) -> Iterator[Event]:
    """Yield the SSE events for one question. The final `done` event also carries `retrieved`."""
    settings = get_settings()
    llm = get_llm()
    history = history or []
    mode = mode or settings.retrieval_mode
    started = time.perf_counter()

    ready = list(
        db.scalars(
            select(Document.id).where(Document.user_id == user.id, Document.status == "ready")
        )
    )
    scope = [d for d in ready if d in set(doc_ids)] if doc_ids else ready
    version = db.scalar(select(User.index_version).where(User.id == user.id)) or 0
    key = cache.answer_key(
        user_id=user.id,
        question=normalize_question(question),
        doc_ids=scope,
        index_version=version,
        mode=mode,
        chat_model=llm.chat_model,
        embedding_model=llm.embedding_model,
        top_k=settings.top_k,
        history_digest=_history_digest(history),
    )

    cached = cache.get_answer(db, key)
    yield _ev("stage", {"stage": "searching"})
    if cached is not None:
        yield _ev("citations", {"citations": cached["citations"]})
        for piece in _replay_chunks(cached["answer"]):
            yield _ev("token", {"text": piece})
        yield _ev(
            "done",
            {
                "answer": cached["answer"],
                "cached": True,
                "mode": mode,
                "not_found": cached["not_found"],
                "rewritten_question": cached.get("rewritten_question"),
                "counts": cached["counts"],
                "timings": {
                    "embed_ms": 0,
                    "retrieve_ms": 0,
                    "rerank_ms": 0,
                    "generate_ms": 0,
                    "total_ms": _ms(started),
                },
                "retrieved": cached.get("retrieved", []),
            },
        )
        return

    rewritten: str | None = None
    effective_q = question
    if history:
        rewritten = llm.rewrite_question(question, history)
        effective_q = rewritten or question
        if effective_q.strip() == question.strip():
            rewritten = None

    timings = {"embed_ms": 0, "retrieve_ms": 0, "rerank_ms": 0, "generate_ms": 0}
    counts = {"retrieved": 0, "fused": 0, "reranked": 0, "used": 0}
    hits: list[Hit] = []
    qualifying: list[Hit] = []

    if scope:
        t = time.perf_counter()
        q_vec = embed_texts(db, llm, [effective_q], batch_size=settings.embed_batch_size)[0]
        timings["embed_ms"] = _ms(t)
        result = retrieval.search(
            user_id=user.id,
            question=effective_q,
            q_vec=q_vec,
            mode=mode,
            doc_ids=scope,
            settings=settings,
        )
        if mode == "hybrid_rerank" and result.hits:
            yield _ev("stage", {"stage": "reranking"})
            retrieval.rerank(result, effective_q, settings, llm)
        retrieval.finalize(result, settings)
        timings["retrieve_ms"] = result.retrieve_ms
        timings["rerank_ms"] = result.rerank_ms
        counts.update(retrieved=result.retrieved, fused=result.fused, reranked=result.reranked)
        hits = result.hits
        qualifying = [h for h in hits if h.score >= result.threshold]

    retrieved_list = [
        {
            "rank": i + 1,
            "doc_id": h.doc_id,
            "filename": h.filename,
            "page_or_section": h.label,
            "score": round(float(h.score), 4),
        }
        for i, h in enumerate(hits)
    ]

    citations: list[dict] = []
    answer_parts: list[str] = []
    not_found = not qualifying

    if not not_found:
        yield _ev("stage", {"stage": "writing"})
        citations = [_citation(i + 1, h, effective_q) for i, h in enumerate(qualifying)]
        passages = [
            ContextPassage(i + 1, h.filename, h.label, h.text) for i, h in enumerate(qualifying)
        ]
        t = time.perf_counter()
        stream = llm.answer_stream(effective_q, passages, history)
        buf = ""
        decided: str | None = None
        try:
            for delta in stream:
                if decided is None:
                    buf += delta
                    probe = buf.lstrip()
                    if len(probe) >= len(NOT_FOUND_SENTINEL):
                        decided = "nf" if probe.startswith(NOT_FOUND_SENTINEL) else "ok"
                    elif not NOT_FOUND_SENTINEL.startswith(probe):
                        decided = "ok"
                    if decided == "ok":
                        yield _ev("citations", {"citations": citations})
                        yield _ev("token", {"text": buf})
                        answer_parts.append(buf)
                    elif decided == "nf":
                        break
                else:
                    answer_parts.append(delta)
                    yield _ev("token", {"text": delta})
        finally:
            close = getattr(stream, "close", None)
            if close:
                close()
        if decided is None:
            if buf.strip() and buf.strip() != NOT_FOUND_SENTINEL:
                decided = "ok"
                yield _ev("citations", {"citations": citations})
                yield _ev("token", {"text": buf})
                answer_parts.append(buf)
            else:
                decided = "nf"
        timings["generate_ms"] = _ms(t)
        not_found = decided == "nf"

    if not_found:
        citations = []
        answer_parts = [NOT_FOUND_MESSAGE]
        yield _ev("citations", {"citations": []})
        yield _ev("token", {"text": NOT_FOUND_MESSAGE})

    answer = "".join(answer_parts).strip()
    counts["used"] = len(citations)
    payload = {
        "answer": answer,
        "citations": citations,
        "not_found": not_found,
        "counts": counts,
        "rewritten_question": rewritten,
        "retrieved": retrieved_list,
    }
    cache.put_answer(db, key, user.id, payload, settings.cache_ttl_seconds)
    timings["total_ms"] = _ms(started)
    yield _ev(
        "done",
        {
            "answer": answer,
            "cached": False,
            "mode": mode,
            "not_found": not_found,
            "rewritten_question": rewritten,
            "counts": counts,
            "timings": timings,
            "retrieved": retrieved_list,
        },
    )

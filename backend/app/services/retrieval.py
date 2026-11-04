"""Vector, hybrid (RRF) and reranked retrieval."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from app.config import Settings
from app.services import bm25_index, vectorstore
from app.services.llm import LLMClient
from app.services.vectorstore import Hit

RRF_K = 60


@dataclass
class RetrievalResult:
    """Final ranked chunks plus the numbers shown in the retrieval trace."""

    hits: list[Hit]
    threshold: float
    retrieved: int = 0
    fused: int = 0
    reranked: int = 0
    retrieve_ms: int = 0
    rerank_ms: int = 0
    reranked_by_llm: bool = False
    extra: dict = field(default_factory=dict)

    @property
    def best_score(self) -> float:
        return max((h.score for h in self.hits), default=0.0)


def rrf_fuse(rankings: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    """Reciprocal Rank Fusion: score(d) = sum over rankings of 1 / (k + rank), rank from 1."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return scores


def _cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return max(0.0, min(1.0, float(va @ vb) / denom)) if denom else 0.0


def search(
    *,
    user_id: str,
    question: str,
    q_vec: list[float],
    mode: str,
    doc_ids: list[str] | None,
    settings: Settings,
) -> RetrievalResult:
    """Candidate retrieval: vector only, or vector + BM25 fused with RRF (top fused_n kept)."""
    started = time.perf_counter()
    vec_hits = vectorstore.query(user_id, q_vec, settings.candidates_n, doc_ids)
    by_id: dict[str, Hit] = {h.id: h for h in vec_hits}

    if mode == "vector":
        ordered = list(vec_hits)
        retrieved = len(vec_hits)
    else:
        bm_hits = bm25_index.search(user_id, question, settings.candidates_n, doc_ids)
        for h in bm_hits:
            by_id.setdefault(h.id, h)
        fused_scores = rrf_fuse([[h.id for h in vec_hits], [h.id for h in bm_hits]])
        ordered_ids = sorted(
            fused_scores,
            key=lambda i: (-fused_scores[i], by_id[i].filename, by_id[i].chunk_index, i),
        )
        ordered = [by_id[i] for i in ordered_ids]
        retrieved = len(by_id)
        # Chunks found only by BM25 have no cosine score yet; compute it from stored vectors.
        seen = {v.id for v in vec_hits}
        missing = [h.id for h in ordered[: settings.fused_n] if h.id not in seen]
        stored = vectorstore.vectors_for(user_id, missing)
        for hit_id in missing:
            if hit_id in stored:
                by_id[hit_id].score = _cosine(q_vec, stored[hit_id])

    fused = ordered[: settings.fused_n]
    return RetrievalResult(
        hits=fused,
        threshold=settings.effective_score_threshold,
        retrieved=retrieved,
        fused=len(fused),
        retrieve_ms=int((time.perf_counter() - started) * 1000),
    )


def rerank(
    result: RetrievalResult, question: str, settings: Settings, llm: LLMClient
) -> RetrievalResult:
    """LLM-score the fused candidates 0-10 and reorder. Malformed output keeps fused order."""
    if not result.hits:
        return result
    started = time.perf_counter()
    scores = llm.rerank_scores(question, [h.text for h in result.hits])
    result.rerank_ms = int((time.perf_counter() - started) * 1000)
    if scores is None:
        return result
    order = sorted(range(len(result.hits)), key=lambda i: (-scores[i], i))
    reordered = [result.hits[i] for i in order]
    for i, hit in zip(order, reordered, strict=True):
        hit.score = round(scores[i] / 10.0, 4)
    result.hits = reordered
    result.threshold = settings.rerank_threshold
    result.reranked_by_llm = True
    return result


def finalize(result: RetrievalResult, settings: Settings) -> RetrievalResult:
    """Keep the top_k chunks."""
    result.hits = result.hits[: settings.top_k]
    result.reranked = len(result.hits)
    return result


def retrieve(
    *,
    user_id: str,
    question: str,
    q_vec: list[float],
    mode: str,
    doc_ids: list[str] | None,
    settings: Settings,
    llm: LLMClient,
) -> RetrievalResult:
    """Run search, optional rerank and top_k selection in one call."""
    result = search(
        user_id=user_id,
        question=question,
        q_vec=q_vec,
        mode=mode,
        doc_ids=doc_ids,
        settings=settings,
    )
    if mode == "hybrid_rerank":
        rerank(result, question, settings, llm)
    return finalize(result, settings)

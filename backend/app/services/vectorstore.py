"""Chroma wrapper. Every query is filtered by user_id."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import get_settings
from app.services.chunking import Chunk

_BATCH = 1000


@dataclass
class Hit:
    """A stored chunk returned from search."""

    id: str
    doc_id: str
    filename: str
    label: str
    text: str
    chunk_index: int
    score: float = 0.0


@lru_cache
def get_client() -> chromadb.ClientAPI:
    settings = get_settings()
    settings.chroma_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(settings.chroma_path),
        settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
    )


@lru_cache
def get_collection() -> chromadb.Collection:
    """One collection per embedding model so vectors of different sizes never mix."""
    settings = get_settings()
    model = "mock-embedding-v1" if settings.mock_llm else f"local:{settings.local_embedding_model}"
    suffix = hashlib.md5(model.encode(), usedforsecurity=False).hexdigest()[:8]
    return get_client().get_or_create_collection(
        name=f"chunks-{suffix}",
        metadata={"hnsw:space": "cosine"},
        embedding_function=None,
    )


def _scope(user_id: str, doc_ids: list[str] | None) -> dict:
    if doc_ids:
        return {"$and": [{"user_id": user_id}, {"doc_id": {"$in": list(doc_ids)}}]}
    return {"user_id": user_id}


def _hit(id_: str, text: str, meta: dict, score: float = 0.0) -> Hit:
    return Hit(
        id=id_,
        doc_id=str(meta["doc_id"]),
        filename=str(meta["filename"]),
        label=str(meta["label"]),
        text=text,
        chunk_index=int(meta["chunk_index"]),
        score=score,
    )


def add_chunks(
    user_id: str, doc_id: str, filename: str, chunks: list[Chunk], vectors: list[list[float]]
) -> None:
    """Replace any existing chunks of the document with the given ones."""
    delete_doc(doc_id)
    col = get_collection()
    for i in range(0, len(chunks), _BATCH):
        part = chunks[i : i + _BATCH]
        col.add(
            ids=[f"{doc_id}:{c.chunk_index}" for c in part],
            documents=[c.text for c in part],
            embeddings=vectors[i : i + _BATCH],
            metadatas=[
                {
                    "user_id": user_id,
                    "doc_id": doc_id,
                    "filename": filename,
                    "label": c.label,
                    "page": c.page if c.page is not None else -1,
                    "section": c.section or "",
                    "chunk_index": c.chunk_index,
                }
                for c in part
            ],
        )


def delete_doc(doc_id: str) -> None:
    get_collection().delete(where={"doc_id": doc_id})


def query(user_id: str, vector: list[float], n: int, doc_ids: list[str] | None = None) -> list[Hit]:
    """Nearest chunks by cosine similarity within the user's (optionally narrowed) documents."""
    col = get_collection()
    total = col.count()
    if total == 0:
        return []
    res = col.query(
        query_embeddings=[vector],
        n_results=min(n, total),
        where=_scope(user_id, doc_ids),
        include=["documents", "metadatas", "distances"],
    )
    hits: list[Hit] = []
    for id_, text, meta, dist in zip(
        res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0], strict=True
    ):
        hits.append(_hit(id_, text, meta, max(0.0, min(1.0, 1.0 - float(dist)))))
    return hits


def all_chunks(user_id: str) -> list[Hit]:
    """Every chunk the user owns (used to build the BM25 index)."""
    res = get_collection().get(where={"user_id": user_id}, include=["documents", "metadatas"])
    hits = [
        _hit(i, t, m)
        for i, t, m in zip(res["ids"], res["documents"], res["metadatas"], strict=True)
    ]
    return sorted(hits, key=lambda h: (h.filename, h.chunk_index, h.doc_id))


def vectors_for(user_id: str, ids: list[str]) -> dict[str, list[float]]:
    """Fetch stored embeddings for specific chunk ids (scoped to the user)."""
    if not ids:
        return {}
    res = get_collection().get(ids=ids, where={"user_id": user_id}, include=["embeddings"])
    return {i: [float(x) for x in e] for i, e in zip(res["ids"], res["embeddings"], strict=True)}


def count_for_doc(doc_id: str) -> int:
    return len(get_collection().get(where={"doc_id": doc_id}, include=[])["ids"])

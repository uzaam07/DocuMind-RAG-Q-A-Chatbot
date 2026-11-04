from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app.db import new_session
from app.models import AnswerCacheEntry, utcnow
from app.services.embeddings import embed_texts
from app.services.llm import get_llm
from tests.conftest import make_pdf, upload

QUESTION = "What are the core hours at Meridian Labs?"


def ask(
    client: TestClient, auth: dict[str, str], question: str = QUESTION, mode: str = "hybrid_rerank"
) -> dict:
    return client.post("/api/ask", headers=auth, json={"question": question, "mode": mode}).json()


def test_second_identical_question_is_a_hit_with_zero_llm_calls(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    first = ask(client, auth)
    assert first["cached"] is False
    llm = get_llm()
    calls_before = llm.total_calls
    second = ask(client, auth, "  what are the CORE hours at meridian labs?  ")
    assert second["cached"] is True
    assert llm.total_calls == calls_before
    assert second["answer"] == first["answer"] and second["citations"] == first["citations"]
    assert second["timings"]["generate_ms"] == 0


def test_mode_is_part_of_the_key(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    ask(client, auth, mode="vector")
    assert ask(client, auth, mode="hybrid")["cached"] is False
    assert ask(client, auth, mode="vector")["cached"] is True


def test_ttl_expiry(client: TestClient, auth: dict[str, str], sample_docs: list[dict]) -> None:
    ask(client, auth)
    with new_session() as db:
        for row in db.query(AnswerCacheEntry).all():
            row.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert ask(client, auth)["cached"] is False
    assert ask(client, auth)["cached"] is True


def test_invalidated_when_a_document_is_added(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    ask(client, auth)
    assert ask(client, auth)["cached"] is True
    upload(client, auth, ("extra.pdf", make_pdf(["Core hours at the annex are nine to five."])))
    assert ask(client, auth)["cached"] is False


def test_invalidated_when_a_document_is_deleted(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    first = ask(client, auth)
    assert ask(client, auth)["cached"] is True
    handbook = next(d for d in sample_docs if d["filename"] == "meridian_handbook.md")
    assert client.delete(f"/api/documents/{handbook['id']}", headers=auth).status_code == 204
    after = ask(client, auth)
    assert after["cached"] is False
    assert all(c["doc_id"] != handbook["id"] for c in after["citations"])
    assert after["answer"] != first["answer"]


def test_embedding_cache_avoids_repeat_calls(client: TestClient) -> None:
    llm = get_llm()
    with new_session() as db:
        embed_texts(db, llm, ["alpha beta", "gamma delta"])
        before = llm.calls["embed"]
        again = embed_texts(db, llm, ["gamma delta", "alpha beta", "gamma delta"])
    assert llm.calls["embed"] == before
    assert len(again) == 3 and again[0] == again[2]


def test_embedding_batches_and_progress(client: TestClient) -> None:
    llm = get_llm()
    seen: list[tuple[int, int]] = []
    with new_session() as db:
        embed_texts(
            db,
            llm,
            [f"text number {i}" for i in range(10)],
            batch_size=4,
            on_progress=lambda d, t: seen.append((d, t)),
        )
    assert seen[0] == (0, 10) and seen[-1] == (10, 10) and len(seen) == 4


def test_stats_reflect_hits_and_misses(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    ask(client, auth)
    ask(client, auth)
    stats = client.get("/api/stats", headers=auth).json()
    assert stats["answer_cache"]["hits"] == 1 and stats["answer_cache"]["misses"] == 1
    assert stats["answer_cache"]["hit_rate"] == 0.5
    assert stats["answer_cache"]["entries"] == 1
    assert stats["embedding_cache"]["entries"] > 0
    assert stats["usage"]["documents"] == 4

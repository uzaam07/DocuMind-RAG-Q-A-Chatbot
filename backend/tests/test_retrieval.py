from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.services import retrieval
from app.services.embeddings import embed_texts
from app.services.llm import get_llm, parse_rerank_scores
from app.services.retrieval import RetrievalResult, rrf_fuse
from app.services.vectorstore import Hit
from tests.conftest import register, upload


def test_rrf_math() -> None:
    scores = rrf_fuse([["a", "b", "c"], ["b", "a", "d"]], k=60)
    assert scores["a"] == pytest.approx(1 / 61 + 1 / 62)
    assert scores["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert scores["c"] == pytest.approx(1 / 63)
    assert scores["d"] == pytest.approx(1 / 63)
    assert scores["a"] > scores["c"]


def test_rrf_rewards_agreement() -> None:
    scores = rrf_fuse([["x", "y"], ["z", "y"]])
    assert max(scores, key=scores.get) == "y"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"scores": [1, 9.5, 0]}', [1.0, 9.5, 0.0]),
        ("```json\n[3, 4, 5]\n```", [3.0, 4.0, 5.0]),
        ('{"scores": [-4, 99, 5]}', [0.0, 10.0, 5.0]),
    ],
)
def test_parse_rerank_valid(raw: str, expected: list[float]) -> None:
    assert parse_rerank_scores(raw, 3) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "not json at all",
        '{"scores": [1, 2]}',
        '{"scores": ["a", "b", "c"]}',
        '{"other": 1}',
        "",
        "null",
    ],
)
def test_parse_rerank_malformed_returns_none(raw: str) -> None:
    assert parse_rerank_scores(raw, 3) is None


def _hits(n: int) -> list[Hit]:
    return [
        Hit(f"id{i}", "d", "f.md", "Section: X", f"text {i}", i, score=0.5 - i / 100)
        for i in range(n)
    ]


class _BrokenReranker:
    def rerank_scores(self, question: str, passages: list[str]) -> None:
        return None


class _ReverseReranker:
    def rerank_scores(self, question: str, passages: list[str]) -> list[float]:
        return [float(i) for i in range(len(passages))]


def test_rerank_malformed_output_keeps_fused_order(env) -> None:  # noqa: ANN001
    settings = get_settings()
    result = RetrievalResult(hits=_hits(4), threshold=0.1, fused=4)
    out = retrieval.rerank(result, "q", settings, _BrokenReranker())  # type: ignore[arg-type]
    assert [h.id for h in out.hits] == ["id0", "id1", "id2", "id3"]
    assert out.reranked_by_llm is False and out.threshold == 0.1


def test_rerank_reorders_and_rescales(env) -> None:  # noqa: ANN001
    settings = get_settings()
    result = RetrievalResult(hits=_hits(4), threshold=0.1, fused=4)
    out = retrieval.rerank(result, "q", settings, _ReverseReranker())  # type: ignore[arg-type]
    assert [h.id for h in out.hits] == ["id3", "id2", "id1", "id0"]
    assert out.hits[0].score == pytest.approx(0.3)
    assert out.reranked_by_llm and out.threshold == settings.rerank_threshold


@pytest.fixture
def indexed(client: TestClient, auth: dict[str, str], sample_docs: list[dict]) -> str:
    return client.get("/api/auth/me", headers=auth).json()["id"]


@pytest.mark.parametrize("mode", ["vector", "hybrid", "hybrid_rerank"])
def test_each_mode_finds_the_right_section(client: TestClient, indexed: str, mode: str) -> None:
    from app.db import new_session

    settings, llm = get_settings(), get_llm()
    question = "How many seconds must the Reset button be held to factory reset the Lumen R2?"
    with new_session() as db:
        q_vec = embed_texts(db, llm, [question])[0]
    result = retrieval.retrieve(
        user_id=indexed,
        question=question,
        q_vec=q_vec,
        mode=mode,
        doc_ids=None,
        settings=settings,
        llm=llm,
    )
    assert result.hits and len(result.hits) <= settings.top_k
    top_labels = [h.label for h in result.hits]
    assert any("reset" in label.lower() for label in top_labels), top_labels
    assert result.retrieved >= result.fused >= result.reranked


def test_hybrid_surfaces_exact_term_matches(client: TestClient, auth: dict[str, str]) -> None:
    upload(
        client,
        auth,
        ("a.txt", b"The vault door code is ZX-4471 and rotates monthly.\n"),
        ("b.txt", b"General notes about the office kitchen and the coffee machine schedule.\n"),
    )
    uid = client.get("/api/auth/me", headers=auth).json()["id"]
    from app.db import new_session

    settings, llm = get_settings(), get_llm()
    with new_session() as db:
        q_vec = embed_texts(db, llm, ["zx-4471"])[0]
    result = retrieval.retrieve(
        user_id=uid,
        question="zx-4471",
        q_vec=q_vec,
        mode="hybrid",
        doc_ids=None,
        settings=settings,
        llm=llm,
    )
    assert result.hits[0].filename == "a.txt"


def test_doc_scope_limits_results(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    pdf = next(d for d in sample_docs if d["file_type"] == "pdf")
    body = client.post(
        "/api/ask",
        headers=auth,
        json={
            "question": "How many seconds must the Reset button be held?",
            "doc_ids": [pdf["id"]],
            "mode": "hybrid",
        },
    ).json()
    assert all(r["filename"] == pdf["filename"] for r in body["retrieved"])


def test_other_users_chunks_never_returned(client: TestClient, indexed: str) -> None:
    from app.services import vectorstore

    other = register(client, "other@example.com")
    other_id = client.get("/api/auth/me", headers=other).json()["id"]
    assert vectorstore.query(other_id, get_llm().embed(["leave days"])[0], 10) == []
    assert vectorstore.all_chunks(other_id) == []

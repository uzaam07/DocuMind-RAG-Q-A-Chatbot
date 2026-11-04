from __future__ import annotations

from fastapi.testclient import TestClient

from app.services import vectorstore
from app.services.llm import get_llm
from tests.conftest import register

QUESTION = "What are the core hours at Meridian Labs?"


def test_user_b_cannot_see_user_a_documents(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    other = register(client, "bob@example.com")
    assert client.get("/api/documents", headers=other).json() == []
    doc_id = sample_docs[0]["id"]
    assert client.get(f"/api/documents/{doc_id}", headers=other).status_code == 404
    assert client.delete(f"/api/documents/{doc_id}", headers=other).status_code == 404
    assert client.post(f"/api/documents/{doc_id}/reindex", headers=other).status_code == 404
    assert client.get(f"/api/documents/{doc_id}", headers=auth).status_code == 200


def test_user_b_cannot_cite_user_a_chunks(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    other = register(client, "bob@example.com")
    for mode in ("vector", "hybrid", "hybrid_rerank"):
        body = client.post(
            "/api/ask", headers=other, json={"question": QUESTION, "mode": mode}
        ).json()
        assert body["not_found"] is True and body["citations"] == [] and body["retrieved"] == []
        forced = client.post(
            "/api/ask",
            headers=other,
            json={"question": QUESTION, "mode": mode, "doc_ids": [d["id"] for d in sample_docs]},
        ).json()
        assert forced["not_found"] is True and forced["citations"] == []


def test_vector_and_bm25_layers_are_user_filtered(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    from app.services import bm25_index

    other = register(client, "bob@example.com")
    other_id = client.get("/api/auth/me", headers=other).json()["id"]
    vec = get_llm().embed([QUESTION])[0]
    assert vectorstore.query(other_id, vec, 20) == []
    assert bm25_index.search(other_id, QUESTION, 20) == []


def test_cached_answers_do_not_leak(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    mine = client.post("/api/ask", headers=auth, json={"question": QUESTION}).json()
    assert mine["not_found"] is False
    other = register(client, "bob@example.com")
    theirs = client.post("/api/ask", headers=other, json={"question": QUESTION}).json()
    assert theirs["cached"] is False and theirs["not_found"] is True and theirs["citations"] == []


def test_sessions_are_private(client: TestClient, auth: dict[str, str]) -> None:
    session = client.post("/api/sessions", headers=auth, json={"title": "private"}).json()
    other = register(client, "bob@example.com")
    assert client.get("/api/sessions", headers=other).json() == []
    for method, url in [
        ("get", f"/api/sessions/{session['id']}/messages"),
        ("delete", f"/api/sessions/{session['id']}"),
    ]:
        assert getattr(client, method)(url, headers=other).status_code == 404
    assert (
        client.patch(
            f"/api/sessions/{session['id']}", headers=other, json={"title": "x"}
        ).status_code
        == 404
    )
    res = client.post(f"/api/sessions/{session['id']}/ask", headers=other, json={"question": "hi"})
    assert res.status_code == 404 and res.json()["error"]["code"] == "not_found"


def test_stats_usage_is_per_user(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    other = register(client, "bob@example.com")
    assert client.get("/api/stats", headers=other).json()["usage"]["documents"] == 0
    assert client.get("/api/stats", headers=auth).json()["usage"]["documents"] == 4


def test_deleting_a_doc_removes_only_that_users_chunks(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    other = register(client, "bob@example.com")
    client.post("/api/documents/sample", headers=other)
    uid_a = client.get("/api/auth/me", headers=auth).json()["id"]
    uid_b = client.get("/api/auth/me", headers=other).json()["id"]
    n_a = len(vectorstore.all_chunks(uid_a))
    victim = client.get("/api/documents", headers=other).json()[0]
    client.delete(f"/api/documents/{victim['id']}", headers=other)
    assert len(vectorstore.all_chunks(uid_a)) == n_a
    assert all(h.doc_id != victim["id"] for h in vectorstore.all_chunks(uid_b))

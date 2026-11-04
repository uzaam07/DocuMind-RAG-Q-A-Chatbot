from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.errors import UpstreamError
from app.services import llm as llm_module
from tests.conftest import make_pdf, read_sse, register, upload

QUESTION = "How many seconds must the Reset button be held to reset the Lumen R2?"


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok", "db": "ok", "chroma": "ok"}


async def test_health_over_async_transport(env) -> None:  # noqa: ANN001
    from app.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get("/health")
    assert res.status_code == 200 and res.json()["status"] == "ok"
    assert "x-request-id" in res.headers


def test_error_envelope_for_unknown_route(client: TestClient) -> None:
    res = client.get("/api/nope")
    assert res.status_code == 404
    assert set(res.json()) == {"error"} and res.json()["error"]["code"] == "not_found"


def test_validation_error_envelope(client: TestClient, auth: dict[str, str]) -> None:
    res = client.post("/api/ask", headers=auth, json={"question": "", "mode": "bogus"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


def test_sse_event_order_and_payload(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    session = client.post("/api/sessions", headers=auth, json={}).json()
    events = read_sse(
        client,
        f"/api/sessions/{session['id']}/ask",
        auth,
        {"question": QUESTION, "mode": "hybrid_rerank"},
    )
    names = [n for n, _ in events]
    assert names[0] == "stage" and names[-1] == "done"
    assert names.count("citations") == 1 and names.count("done") == 1
    first_token = names.index("token")
    assert names.index("citations") < first_token
    assert {d["stage"] for n, d in events if n == "stage"} >= {"searching", "reranking", "writing"}
    assert all(n in {"stage", "citations", "token", "done"} for n in names)
    done = events[-1][1]
    assert done["answer"] == "".join(d["text"] for n, d in events if n == "token").strip()
    assert set(done["counts"]) == {"retrieved", "fused", "reranked", "used"}
    assert set(done["timings"]) == {
        "embed_ms",
        "retrieve_ms",
        "rerank_ms",
        "generate_ms",
        "total_ms",
    }
    assert (
        done["cached"] is False and done["mode"] == "hybrid_rerank" and done["not_found"] is False
    )
    assert "retrieved" not in done and done["message_id"]


def test_sse_cache_hit_replays_same_shape(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    # A repeat inside the same chat has different prior turns, so the cache key differs by design;
    # the same question in a fresh chat has identical context and hits the cache.
    a = client.post("/api/sessions", headers=auth, json={}).json()
    b = client.post("/api/sessions", headers=auth, json={}).json()
    first = read_sse(
        client, f"/api/sessions/{a['id']}/ask", auth, {"question": QUESTION, "mode": "hybrid"}
    )
    second = read_sse(
        client, f"/api/sessions/{b['id']}/ask", auth, {"question": QUESTION, "mode": "hybrid"}
    )
    assert second[-1][1]["cached"] is True
    assert [n for n, _ in second][0] == "stage" and [n for n, _ in second][-1] == "done"
    assert second[-1][1]["answer"] == first[-1][1]["answer"]
    assert "reranking" not in {d["stage"] for n, d in second if n == "stage"}


def test_sse_not_found_shape(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    session = client.post("/api/sessions", headers=auth, json={}).json()
    events = read_sse(
        client,
        f"/api/sessions/{session['id']}/ask",
        auth,
        {
            "question": "How much is the monthly gym membership subsidy at Meridian Labs?",
            "mode": "vector",
        },
    )
    citations = next(d for n, d in events if n == "citations")
    done = events[-1][1]
    assert (
        done["not_found"] is True and citations["citations"] == [] and done["counts"]["used"] == 0
    )
    assert [n for n, _ in events].count("token") >= 1


def test_sse_error_event_on_provider_failure(
    client: TestClient,
    auth: dict[str, str],
    sample_docs: list[dict],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_a: object, **_k: object):  # noqa: ANN202
        raise UpstreamError("The model provider did not respond in time. Try again shortly.")
        yield  # pragma: no cover

    monkeypatch.setattr(llm_module.get_llm(), "answer_stream", boom)
    session = client.post("/api/sessions", headers=auth, json={}).json()
    events = read_sse(
        client, f"/api/sessions/{session['id']}/ask", auth, {"question": QUESTION, "mode": "vector"}
    )
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == "upstream_unavailable"
    assert "done" not in [n for n, _ in events]


def test_ask_json_surfaces_upstream_errors_as_envelope(
    client: TestClient,
    auth: dict[str, str],
    sample_docs: list[dict],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_a: object, **_k: object):  # noqa: ANN202
        raise UpstreamError("rate limited", status=429, code="rate_limited")
        yield  # pragma: no cover

    monkeypatch.setattr(llm_module.get_llm(), "answer_stream", boom)
    res = client.post("/api/ask", headers=auth, json={"question": QUESTION, "mode": "vector"})
    assert res.status_code == 429 and res.json()["error"]["code"] == "rate_limited"


def test_session_crud_and_history(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    session = client.post("/api/sessions", headers=auth, json={}).json()
    assert session["title"] == "New chat"
    read_sse(
        client, f"/api/sessions/{session['id']}/ask", auth, {"question": QUESTION, "mode": "hybrid"}
    )
    renamed = client.patch(
        f"/api/sessions/{session['id']}", headers=auth, json={"title": "Router"}
    ).json()
    assert renamed["title"] == "Router"
    messages = client.get(f"/api/sessions/{session['id']}/messages", headers=auth).json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assistant = messages[1]
    assert assistant["citations"] and assistant["meta"]["counts"]["used"] == len(
        assistant["citations"]
    )
    assert assistant["meta"]["message_id"] == assistant["id"]
    auto = client.post("/api/sessions", headers=auth, json={}).json()
    read_sse(
        client, f"/api/sessions/{auto['id']}/ask", auth, {"question": "What are the core hours?"}
    )
    titles = {s["title"] for s in client.get("/api/sessions", headers=auth).json()}
    assert "What are the core hours?" in titles and "Router" in titles
    assert client.delete(f"/api/sessions/{session['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/sessions/{session['id']}/messages", headers=auth).status_code == 404


def test_sample_endpoint_is_idempotent(client: TestClient, auth: dict[str, str]) -> None:
    first = client.post("/api/documents/sample", headers=auth).json()
    second = client.post("/api/documents/sample", headers=auth).json()
    assert len(first) == 4 and {d["id"] for d in first} == {d["id"] for d in second}
    docs = client.get("/api/documents", headers=auth).json()
    assert len(docs) == 4 and all(d["status"] == "ready" and d["chunk_count"] > 0 for d in docs)


def test_delete_and_reindex(client: TestClient, auth: dict[str, str]) -> None:
    [doc] = upload(client, auth, ("note.txt", b"Quarterly offsite is in March.\n"))
    redo = client.post(f"/api/documents/{doc['id']}/reindex", headers=auth)
    assert redo.status_code == 202
    after = client.get(f"/api/documents/{doc['id']}", headers=auth).json()
    assert after["status"] == "ready" and after["stage"] == "done"
    assert client.delete(f"/api/documents/{doc['id']}", headers=auth).status_code == 204
    assert client.get("/api/documents", headers=auth).json() == []


def test_reindex_of_rejected_file_conflicts(client: TestClient, auth: dict[str, str]) -> None:
    [doc] = upload(client, auth, ("x.exe", b"MZ"))
    res = client.post(f"/api/documents/{doc['id']}/reindex", headers=auth)
    assert res.status_code == 409 and res.json()["error"]["code"] == "conflict"


def test_failed_pdf_can_be_replaced(client: TestClient, auth: dict[str, str]) -> None:
    [bad] = upload(client, auth, ("a.pdf", make_pdf(["", ""])))
    docs = {d["id"]: d for d in client.get("/api/documents", headers=auth).json()}
    assert docs[bad["id"]]["status"] == "failed"
    assert client.post(f"/api/documents/{bad['id']}/reindex", headers=auth).status_code == 202


def test_eval_latest(client: TestClient, auth: dict[str, str], env) -> None:  # noqa: ANN001
    assert client.get("/api/eval/latest", headers=auth).json() == {"available": False}
    (env / "results.json").write_text(json.dumps({"mock": True, "k": 5, "modes": {}}))
    body = client.get("/api/eval/latest", headers=auth).json()
    assert body["available"] is True and body["mock"] is True


def test_missing_api_key_fails_fast(monkeypatch: pytest.MonkeyPatch, env) -> None:  # noqa: ANN001
    from app.runtime import reset_runtime

    monkeypatch.setenv("MOCK_LLM", "false")
    reset_runtime()
    from app.main import create_app

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"), TestClient(create_app()):
        pass


def test_interrupted_indexing_is_recovered_on_startup(env) -> None:  # noqa: ANN001
    from app.db import init_db, new_session
    from app.main import create_app
    from app.models import Document, User

    init_db()
    with new_session() as db:
        user = User(email="x@example.com", password_hash="x")
        db.add(user)
        db.commit()
        db.add(
            Document(
                user_id=user.id,
                filename="a.txt",
                file_type="txt",
                status="processing",
                stage="embedding",
            )
        )
        db.commit()
    with TestClient(create_app()):
        pass
    with new_session() as db:
        doc = db.query(Document).one()
    assert doc.status == "failed" and "interrupted" in doc.error


def test_search_feedback_and_export_are_owner_scoped(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    session = client.post(
        "/api/sessions", headers=auth, json={"title": "Quarterly research"}
    ).json()
    events = read_sse(
        client, f"/api/sessions/{session['id']}/ask", auth,
        {"question": "Summarize the router reset procedure", "mode": "hybrid"},
    )
    results = client.get("/api/sessions/search", headers=auth, params={"q": "router reset"})
    assert results.status_code == 200 and results.json()[0]["session_id"] == session["id"]
    messages = client.get(f"/api/sessions/{session['id']}/messages", headers=auth).json()
    assistant = messages[-1]
    feedback = client.post(
        f"/api/messages/{assistant['id']}/feedback",
        headers=auth,
        json={"rating": "helpful"},
    )
    assert feedback.status_code == 200 and feedback.json()["rating"] == "helpful"
    exported = client.get(f"/api/sessions/{session['id']}/export", headers=auth)
    assert exported.status_code == 200 and "Quarterly research" in exported.json()["markdown"]
    other = register(client, "grace@example.com")
    assert (
        client.get("/api/sessions/search", headers=other, params={"q": "router reset"}).json()
        == []
    )
    assert (
        client.post(
            f"/api/messages/{assistant['id']}/feedback",
            headers=other,
            json={"rating": "not_helpful"},
        ).status_code
        == 404
    )

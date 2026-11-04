from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.llm import NOT_FOUND_MESSAGE
from tests.conftest import read_sse

QUESTION = "How long must the Reset button be held to reset the Lumen R2 to factory settings?"


def ask(
    client: TestClient, auth: dict[str, str], question: str = QUESTION, **extra: object
) -> dict:
    res = client.post("/api/ask", headers=auth, json={"question": question, **extra})
    assert res.status_code == 200, res.text
    return res.json()


def test_grounded_answer_has_citations(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    body = ask(client, auth)
    assert not body["not_found"] and body["citations"]
    assert "[" in body["answer"] and "]" in body["answer"]
    cite = body["citations"][0]
    assert cite["filename"] == "lumen_router_faq.docx"
    assert cite["page_or_section"].startswith("Section: ")
    assert cite["snippet"] and cite["highlight"] in cite["snippet"]
    assert 0 <= cite["score"] <= 1
    assert body["counts"]["used"] == len(body["citations"])


def test_every_marker_matches_a_citation(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    import re

    body = ask(client, auth)
    ids = {c["id"] for c in body["citations"]}
    markers = {int(m) for m in re.findall(r"\[(\d+)\]", body["answer"])}
    assert markers and markers <= ids


def test_unanswerable_question_falls_back(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    body = ask(
        client, auth, "Which cloud provider hosts the Harbor Queue cluster?", mode="hybrid_rerank"
    )
    assert body["not_found"] is True
    assert body["answer"] == NOT_FOUND_MESSAGE
    assert body["citations"] == [] and body["counts"]["used"] == 0


def test_no_documents_means_not_found(client: TestClient, auth: dict[str, str]) -> None:
    body = ask(client, auth)
    assert body["not_found"] and body["retrieved"] == []


def test_score_threshold_triggers_fallback(
    env,
    monkeypatch,
    auth=None,  # noqa: ANN001
) -> None:
    monkeypatch.setenv("SCORE_THRESHOLD", "0.99")
    monkeypatch.setenv("RERANK_THRESHOLD", "0.99")
    from app.runtime import reset_runtime

    reset_runtime()
    from fastapi.testclient import TestClient as TC

    from app.main import create_app
    from tests.conftest import register

    with TC(create_app()) as client:
        headers = register(client)
        client.post("/api/documents/sample", headers=headers)
        for mode in ("vector", "hybrid", "hybrid_rerank"):
            body = ask(client, headers, mode=mode)
            assert body["not_found"] is True, mode


def test_modes_report_funnel_counts(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    vector = ask(client, auth, mode="vector")
    rerank = ask(client, auth, mode="hybrid_rerank")
    assert (
        vector["counts"]["retrieved"] >= vector["counts"]["fused"] >= vector["counts"]["reranked"]
    )
    assert rerank["timings"]["rerank_ms"] >= 0 and rerank["mode"] == "hybrid_rerank"
    assert vector["timings"]["total_ms"] >= 0


def test_follow_up_is_rewritten_and_used(
    client: TestClient, auth: dict[str, str], sample_docs: list[dict]
) -> None:
    session = client.post("/api/sessions", headers=auth, json={}).json()
    url = f"/api/sessions/{session['id']}/ask"
    first = read_sse(client, url, auth, {"question": QUESTION, "mode": "hybrid"})
    assert first[-1][1]["rewritten_question"] is None
    follow = read_sse(
        client, url, auth, {"question": "And how long does the update take?", "mode": "hybrid"}
    )
    done = follow[-1][1]
    assert done["rewritten_question"] and "regarding" in done["rewritten_question"]
    assert "Reset" in done["rewritten_question"]

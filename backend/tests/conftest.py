"""Shared fixtures. Every test runs offline against a throwaway data directory."""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.runtime import reset_runtime

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = ROOT / "eval" / "sample_docs"


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Configure environment variables for an isolated mock-LLM app."""
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("JWT_SECRET", "test-secret-test-secret-test-secret")
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    monkeypatch.setenv("SAMPLE_DOCS_DIR", str(SAMPLE_DIR))
    monkeypatch.setenv("EVAL_RESULTS_PATH", str(tmp_path / "results.json"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("SCORE_THRESHOLD", raising=False)
    reset_runtime()
    yield tmp_path
    reset_runtime()


@pytest.fixture
def client(env: Path) -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


def register(client: TestClient, email: str = "ada@example.com") -> dict[str, str]:
    """Create a user and return auth headers."""
    res = client.post("/api/auth/register", json={"email": email, "password": "correct horse"})
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def auth(client: TestClient) -> dict[str, str]:
    return register(client)


@pytest.fixture
def sample_docs(client: TestClient, auth: dict[str, str]) -> list[dict]:
    """The bundled sample documents, indexed for the default user."""
    res = client.post("/api/documents/sample", headers=auth)
    assert res.status_code == 200, res.text
    docs = client.get("/api/documents", headers=auth).json()
    assert len(docs) == 4 and all(d["status"] == "ready" for d in docs), docs
    return docs


def make_pdf(pages: list[str]) -> bytes:
    """Build a real text PDF; an empty string yields a page with no text (like a scan)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    for text in pages:
        y = 800
        for line in text.splitlines():
            pdf.drawString(60, y, line)
            y -= 16
        pdf.showPage()
    pdf.save()
    return buf.getvalue()


def make_docx(blocks: list[tuple[str, str]]) -> bytes:
    """Build a DOCX; blocks are (style, text) such as ('Heading 1', 'Intro')."""
    from docx import Document

    doc = Document()
    for style, text in blocks:
        if style.startswith("Heading"):
            doc.add_heading(text, level=int(style.split()[-1]))
        else:
            doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def upload(client: TestClient, headers: dict[str, str], *files: tuple[str, bytes]) -> list[dict]:
    payload = [("files", (name, data, "application/octet-stream")) for name, data in files]
    res = client.post("/api/documents", headers=headers, files=payload)
    assert res.status_code == 202, res.text
    return res.json()


def read_sse(
    client: TestClient, url: str, headers: dict[str, str], body: dict
) -> list[tuple[str, dict]]:
    """POST and parse the SSE stream into (event, data) pairs."""
    events: list[tuple[str, dict]] = []
    with client.stream("POST", url, headers=headers, json=body) as res:
        assert res.status_code == 200, res.read()
        assert res.headers["content-type"].startswith("text/event-stream")
        text = "".join(res.iter_text())
    for frame in text.strip().split("\n\n"):
        lines = frame.split("\n")
        assert lines[0].startswith("event: ") and lines[1].startswith("data: "), frame
        events.append((lines[0][7:], json.loads(lines[1][6:])))
    return events

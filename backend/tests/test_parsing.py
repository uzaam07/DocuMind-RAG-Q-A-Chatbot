from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services.parsing import (
    ParseError,
    check_signature,
    file_type_for,
    parse_file,
    sanitize_filename,
)
from tests.conftest import make_docx, make_pdf, upload


def test_markdown_sections(tmp_path: Path) -> None:
    path = tmp_path / "a.md"
    path.write_text("# Title\nintro text\n\n## Leave\nTwenty days.\n\n## Pay\nMonthly.\n")
    blocks = parse_file(path, "md")
    assert [b.section for b in blocks] == ["Title", "Leave", "Pay"]
    assert "Twenty days." in blocks[1].text


def test_text_uppercase_headings(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_text(
        "Runbook title\n\nSEVERITY LEVELS\n\nSev1 is critical.\n\nON CALL\n\nPage the lead.\n"
    )
    blocks = parse_file(path, "txt")
    assert [b.section for b in blocks] == [None, "SEVERITY LEVELS", "ON CALL"]


def test_docx_heading_styles(tmp_path: Path) -> None:
    path = tmp_path / "a.docx"
    path.write_bytes(
        make_docx(
            [
                ("Heading 1", "Setup"),
                ("p", "Plug it in."),
                ("Heading 1", "Reset"),
                ("p", "Hold ten seconds."),
            ]
        )
    )
    blocks = parse_file(path, "docx")
    assert [b.section for b in blocks] == ["Setup", "Reset"]
    assert "Hold ten seconds." in blocks[1].text


def test_pdf_pages(tmp_path: Path) -> None:
    path = tmp_path / "a.pdf"
    path.write_bytes(make_pdf(["Page one text about keys", "Page two text about limits"]))
    blocks = parse_file(path, "pdf")
    assert [b.page for b in blocks] == [1, 2]
    assert "limits" in blocks[1].text


def test_scanned_pdf_without_text_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "scan.pdf"
    path.write_bytes(make_pdf(["", ""]))
    with pytest.raises(ParseError, match="no selectable text"):
        parse_file(path, "pdf")


def test_corrupt_pdf_raises_readable_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"%PDF-1.4\nthis is not a real pdf body")
    with pytest.raises(ParseError, match="could not be read"):
        parse_file(path, "pdf")


def test_signature_checks() -> None:
    assert check_signature("pdf", b"hello") is not None
    assert check_signature("pdf", b"%PDF-1.7 ...") is None
    assert check_signature("docx", b"plain") is not None
    assert check_signature("docx", make_docx([("p", "x")])) is None
    assert check_signature("txt", b"abc\x00def") is not None


def test_filename_helpers() -> None:
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("C:\\temp\\report.pdf") == "report.pdf"
    assert sanitize_filename("a\x00b\n.txt") == "ab.txt"
    assert file_type_for("X.PDF") == "pdf" and file_type_for("x.exe") == "unknown"


def test_upload_rejects_wrong_extension(client: TestClient, auth: dict[str, str]) -> None:
    [doc] = upload(client, auth, ("malware.exe", b"MZ..."))
    assert doc["status"] == "failed" and "Unsupported file type" in doc["error"]


def test_upload_rejects_empty_file(client: TestClient, auth: dict[str, str]) -> None:
    [doc] = upload(client, auth, ("empty.txt", b""))
    assert doc["status"] == "failed" and "empty" in doc["error"]


def test_upload_rejects_signature_mismatch(client: TestClient, auth: dict[str, str]) -> None:
    [doc] = upload(client, auth, ("fake.pdf", b"just some text"))
    assert doc["status"] == "failed" and "PDF" in doc["error"]


def test_upload_rejects_oversize(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    from app.runtime import reset_runtime

    reset_runtime()
    from fastapi.testclient import TestClient as TC

    from app.main import create_app
    from tests.conftest import register

    with TC(create_app()) as client:
        headers = register(client)
        [doc] = upload(client, headers, ("big.txt", b"a" * (1024 * 1024 + 10)))
    assert doc["status"] == "failed" and "larger than 1 MB" in doc["error"]


def test_upload_scanned_pdf_ends_failed_with_reason(
    client: TestClient, auth: dict[str, str]
) -> None:
    upload(client, auth, ("scan.pdf", make_pdf(["", ""])))
    [doc] = client.get("/api/documents", headers=auth).json()
    assert doc["status"] == "failed"
    assert "no selectable text" in doc["error"]


def test_upload_valid_files_become_ready(client: TestClient, auth: dict[str, str]) -> None:
    upload(
        client,
        auth,
        ("a.md", b"# Leave\nTwenty five days of annual leave."),
        ("b.txt", b"Plain notes about the quarterly offsite.\n"),
        ("c.pdf", make_pdf(["Alpha beta gamma"])),
        ("d.docx", make_docx([("Heading 1", "Intro"), ("p", "Hello world")])),
    )
    docs = client.get("/api/documents", headers=auth).json()
    assert len(docs) == 4
    assert all(d["status"] == "ready" and d["chunk_count"] >= 1 for d in docs), docs
    assert {d["file_type"] for d in docs} == {"md", "txt", "pdf", "docx"}


def test_xlsx_sheet_content_and_location(tmp_path: Path) -> None:
    from openpyxl import Workbook
    path = tmp_path / "metrics.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Revenue"
    sheet.append(["Quarter", "Revenue"])
    sheet.append(["Q1", 1200])
    workbook.save(path)
    blocks = parse_file(path, "xlsx")
    assert blocks[0].section == "Sheet: Revenue"
    assert "Q1 | 1200" in blocks[0].text


def test_pptx_slide_content_and_location(tmp_path: Path) -> None:
    from pptx import Presentation
    from pptx.util import Inches
    path = tmp_path / "briefing.pptx"
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1)).text = "Quarterly plan"
    presentation.save(path)
    blocks = parse_file(path, "pptx")
    assert blocks[0].page == 1 and blocks[0].section == "Slide 1"
    assert "Quarterly plan" in blocks[0].text


def test_html_parser_removes_active_content(tmp_path: Path) -> None:
    path = tmp_path / "brief.html"
    html = (
        "<html><head><title>Brief</title><script>alert(1)</script></head>"
        "<body><main><h1>Plan</h1><p>Launch safely.</p></main>"
        "<footer>Footer noise</footer></body></html>"
    )
    path.write_text(html)
    blocks = parse_file(path, "html")
    assert blocks[0].section == "Brief"
    assert "Launch safely" in blocks[0].text
    assert "alert(1)" not in blocks[0].text and "Footer noise" not in blocks[0].text

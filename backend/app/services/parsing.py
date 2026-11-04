"""File validation and extraction for text, office, web and image documents."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

ALLOWED_TYPES = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
    ".md": "md",
    ".xlsx": "xlsx",
    ".pptx": "pptx",
    ".html": "html",
    ".htm": "html",
    ".png": "png",
    ".jpg": "jpg",
    ".jpeg": "jpeg",
    ".webp": "webp",
}
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_HEADING_MD = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")


class ParseError(Exception):
    """A document cannot be read; the message is safe to show to the user."""


@dataclass
class Block:
    """A run of text that shares one location label (a page or a section)."""

    text: str
    page: int | None = None
    section: str | None = None


def sanitize_filename(name: str) -> str:
    """Strip directories and control characters; never used as a filesystem path."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = _CONTROL.sub("", base).strip().strip(".")
    return (base or "untitled")[:200]


def file_type_for(filename: str) -> str:
    """Return the file type for a filename extension, or 'unknown'."""
    return ALLOWED_TYPES.get(Path(filename).suffix.lower(), "unknown")


def check_signature(file_type: str, data: bytes) -> str | None:
    """Return a user-facing problem if the bytes do not match the claimed type."""
    if file_type == "pdf" and not data.lstrip()[:5].startswith(b"%PDF"):
        return "This file does not look like a PDF. Export it as a PDF and upload again."
    if file_type in {"docx", "xlsx", "pptx"}:
        if not data.startswith(b"PK"):
            return (
                f"This file does not look like a valid {file_type.upper()} document. "
                "Save it again and upload."
            )
        try:
            import io

            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                required = {
                    "docx": "word/document.xml",
                    "xlsx": "xl/workbook.xml",
                    "pptx": "ppt/presentation.xml",
                }[file_type]
                if required not in zf.namelist():
                    return (
                        f"This {file_type.upper()} file is missing its document structure. "
                        "Re-save it and upload again."
                    )
        except zipfile.BadZipFile:
            return f"This {file_type.upper()} file is corrupted. Re-save it and upload again."
    if file_type in {"png", "jpg", "jpeg", "webp"}:
        signatures = {
            "png": b"\x89PNG\r\n\x1a\n",
            "jpg": b"\xff\xd8\xff",
            "jpeg": b"\xff\xd8\xff",
            "webp": b"RIFF",
        }
        is_webp = file_type == "webp" and data[8:12] != b"WEBP"
        if not data.startswith(signatures[file_type]) or is_webp:
            return "The image contents do not match the selected file type."
    if file_type in {"txt", "md"} and b"\x00" in data[:4096]:
        return "This file is binary, not text. Upload a plain text or Markdown file."
    return None


def clean_text(text: str) -> str:
    """Normalise newlines, remove control characters and collapse runs of whitespace."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_file(path: Path, file_type: str) -> list[Block]:
    """Extract labelled text blocks from a stored file."""
    try:
        if file_type == "pdf":
            blocks = _parse_pdf(path)
        elif file_type == "docx":
            blocks = _parse_docx(path)
        elif file_type == "md":
            blocks = _parse_headed(_read_text(path), _md_heading)
        elif file_type == "txt":
            blocks = _parse_headed(_read_text(path), None)
        elif file_type == "xlsx":
            blocks = _parse_xlsx(path)
        elif file_type == "pptx":
            blocks = _parse_pptx(path)
        elif file_type == "html":
            blocks = _parse_html(path)
        elif file_type in {"png", "jpg", "jpeg", "webp"}:
            blocks = _parse_image_ocr(path)
        else:
            raise ParseError(
                "Unsupported file type. Upload PDF, DOCX, TXT, MD, XLSX, PPTX, HTML "
                "or PNG/JPG/WEBP images."
            )
    except ParseError:
        raise
    except Exception as exc:
        raise ParseError(
            f"This {file_type.upper()} could not be read ({type(exc).__name__}). "
            "It may be corrupted; export it again and upload."
        ) from exc
    blocks = [Block(clean_text(b.text), b.page, b.section) for b in blocks]
    blocks = [b for b in blocks if b.text]
    if not blocks and file_type == "pdf":
        blocks = _ocr_pdf(path)
    if not blocks:
        if file_type == "pdf":
            raise ParseError(
                "This PDF has no selectable text. Install Tesseract OCR and the PDF "
                "renderer, then reindex it."
            )
        raise ParseError("This file has no readable text. Add content and upload again.")
    return blocks


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def _parse_xlsx(path: Path) -> list[Block]:
    from openpyxl import load_workbook

    workbook = load_workbook(path, read_only=True, data_only=True)
    blocks: list[Block] = []
    try:
        for sheet in workbook.worksheets:
            rows = []
            for row in sheet.iter_rows(values_only=True):
                values = [
                    str(value).strip()
                    for value in row
                    if value is not None and str(value).strip()
                ]
                if values:
                    rows.append(" | ".join(values))
            if rows:
                blocks.append(Block("\n".join(rows), section=f"Sheet: {sheet.title}"))
    finally:
        workbook.close()
    return blocks


def _parse_pptx(path: Path) -> list[Block]:
    from pptx import Presentation

    presentation = Presentation(str(path))
    blocks: list[Block] = []
    for index, slide in enumerate(presentation.slides, start=1):
        lines = []
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False) and shape.text.strip():
                lines.append(shape.text.strip())
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if cells:
                        lines.append(" | ".join(cells))
        if lines:
            blocks.append(Block("\n".join(lines), page=index, section=f"Slide {index}"))
    return blocks


def _parse_html(path: Path) -> list[Block]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    for node in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
        node.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else path.name
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text("\n", strip=True)
    return [Block(f"{title}\n\n{text}", section=title)] if text else []


def _parse_image_ocr(path: Path) -> list[Block]:
    try:
        from PIL import Image
        import pytesseract
        with Image.open(path) as image:
            text = pytesseract.image_to_string(image)
    except Exception as exc:
        raise ParseError(
            "Image OCR is unavailable. Install Tesseract OCR and the Python image "
            "dependencies, then reindex."
        ) from exc
    return [Block(text, section="OCR extracted text")] if text.strip() else []


def _parse_pdf(path: Path) -> list[Block]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    if reader.is_encrypted:
        raise ParseError("This PDF is password protected. Remove the password and upload again.")
    return [Block(page.extract_text() or "", page=i + 1) for i, page in enumerate(reader.pages)]


def _ocr_pdf(path: Path) -> list[Block]:
    """OCR scanned PDF pages when the optional PDFium and Tesseract runtimes exist."""
    try:
        import pytesseract
        import pypdfium2 as pdfium
        document = pdfium.PdfDocument(str(path))
        blocks: list[Block] = []
        try:
            for index, page in enumerate(document, start=1):
                bitmap = page.render(scale=2)
                image = bitmap.to_pil()
                text = pytesseract.image_to_string(image)
                if text.strip():
                    blocks.append(Block(text, page=index))
                image.close()
                page.close()
        finally:
            document.close()
        return blocks
    except Exception as exc:
        raise ParseError(
            "This PDF has no selectable text; OCR needs the PDFium and Tesseract "
            "runtimes. Install them on the server and reindex."
        ) from exc


def _parse_docx(path: Path) -> list[Block]:
    from docx import Document

    doc = Document(str(path))
    lines: list[tuple[str | None, str]] = []  # (heading or None, text)
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name if para.style is not None else "") or ""
        lines.append((text if style.startswith("Heading") else None, text))
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                lines.append((None, " | ".join(cells)))
    blocks: list[Block] = []
    current: Block | None = None
    for heading, text in lines:
        if heading is not None:
            current = Block(text=heading, section=heading)
            blocks.append(current)
        else:
            if current is None:
                current = Block(text="")
                blocks.append(current)
            current.text += ("\n\n" if current.text else "") + text
    return blocks


def _md_heading(line: str) -> str | None:
    match = _HEADING_MD.match(line)
    return match.group(1).strip() if match else None


def _txt_heading(lines: list[str], i: int) -> str | None:
    line = lines[i].strip()
    if not 3 <= len(line) <= 80 or line != line.upper():
        return None
    if sum(c.isalpha() for c in line) < 3:
        return None
    if i + 1 < len(lines) and lines[i + 1].strip():
        return None
    return line


def _parse_headed(text: str, md_detector) -> list[Block]:  # type: ignore[no-untyped-def]
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[Block] = []
    current = Block(text="")
    for i, line in enumerate(lines):
        heading = md_detector(line) if md_detector else _txt_heading(lines, i)
        if heading is not None:
            if current.text.strip():
                blocks.append(current)
            current = Block(text=heading + "\n", section=heading)
        else:
            current.text += line + "\n"
    if current.text.strip():
        blocks.append(current)
    return blocks

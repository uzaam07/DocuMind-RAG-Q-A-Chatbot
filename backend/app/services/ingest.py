"""Document intake and the background indexing pipeline."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import new_session
from app.errors import UpstreamError
from app.logging_setup import get_logger
from app.models import Document, User, new_id, utcnow
from app.services import bm25_index, cache, vectorstore
from app.services.chunking import chunk_blocks
from app.services.embeddings import embed_texts
from app.services.llm import get_llm
from app.services.parsing import (
    ParseError,
    check_signature,
    file_type_for,
    parse_file,
    sanitize_filename,
)

log = get_logger(__name__)

UNSUPPORTED = "Unsupported file type. Upload PDF, DOCX, TXT, MD, XLSX, PPTX, HTML or PNG/JPG/WEBP images."


def bump_index_version(db: Session, user_id: str) -> None:
    """Invalidate cached answers and the BM25 index after the user's documents change."""
    db.execute(update(User).where(User.id == user_id).values(index_version=User.index_version + 1))
    db.commit()
    cache.purge_user_answers(db, user_id)
    bm25_index.invalidate(user_id)


def create_document(
    db: Session, user: User, filename: str, data: bytes, settings: Settings
) -> tuple[Document, bool]:
    """Validate and store an upload. Returns the row and whether indexing should be queued.

    Rejected files still produce a `failed` row so the UI can show the reason inline.
    """
    name = sanitize_filename(filename)
    file_type = file_type_for(name)
    doc = Document(
        id=new_id(),
        user_id=user.id,
        filename=name,
        file_type=file_type,
        size_bytes=len(data),
        status="processing",
        stage="queued",
    )
    problem: str | None
    if file_type == "unknown":
        problem = UNSUPPORTED
    elif not data:
        problem = "This file is empty. Add content and upload again."
    elif len(data) > settings.max_upload_bytes:
        problem = f"This file is larger than {settings.max_upload_mb} MB. Upload a smaller file."
    else:
        problem = check_signature(file_type, data)
    if problem:
        doc.status, doc.stage, doc.error = "failed", "done", problem
        db.add(doc)
        db.commit()
        return doc, False
    folder = settings.uploads_path / user.id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{doc.id}.{file_type}"
    path.write_bytes(data)
    doc.storage_path = str(path)
    db.add(doc)
    db.commit()
    return doc, True


def remove_document(db: Session, doc: Document) -> None:
    """Delete a document's chunks, stored file and row, then invalidate caches."""
    vectorstore.delete_doc(doc.id)
    if doc.storage_path:
        Path(doc.storage_path).unlink(missing_ok=True)
    user_id = doc.user_id
    db.delete(doc)
    db.commit()
    bump_index_version(db, user_id)


def _fail(db: Session, doc: Document, message: str) -> None:
    doc.status, doc.error, doc.updated_at = "failed", message, utcnow()
    db.commit()


def recover_interrupted() -> int:
    """Mark documents left in `processing` by a crash or restart as failed (reindex fixes them)."""
    db = new_session()
    try:
        stuck = list(db.scalars(select(Document).where(Document.status == "processing")))
        for doc in stuck:
            _fail(db, doc, "Indexing was interrupted by a server restart. Use Reindex to retry.")
        return len(stuck)
    finally:
        db.close()


def ingest_document(doc_id: str) -> None:
    """Parse, chunk, embed and index one stored document. Never raises."""
    db = new_session()
    try:
        doc = db.get(Document, doc_id)
        if doc is None or not doc.storage_path:
            return
        settings = get_settings()

        def stage(name: str, **fields: object) -> None:
            doc.stage = name
            for k, v in fields.items():
                setattr(doc, k, v)
            doc.updated_at = utcnow()
            db.commit()

        try:
            stage("parsing", status="processing", error=None, progress_done=0, progress_total=0)
            blocks = parse_file(Path(doc.storage_path), doc.file_type)
            stage("chunking")
            chunks = chunk_blocks(blocks, settings.chunk_size, settings.chunk_overlap)
            if not chunks:
                raise ParseError("This file has no readable text. Add content and upload again.")
            stage("embedding", progress_done=0, progress_total=len(chunks))

            def progress(done: int, total: int) -> None:
                doc.progress_done, doc.progress_total = done, total
                db.commit()

            vectors = embed_texts(
                db,
                get_llm(),
                [c.text for c in chunks],
                batch_size=settings.embed_batch_size,
                on_progress=progress,
            )
            stage("indexing")
            vectorstore.add_chunks(doc.user_id, doc.id, doc.filename, chunks, vectors)
            stage(
                "done",
                status="ready",
                chunk_count=len(chunks),
                progress_done=len(chunks),
                progress_total=len(chunks),
            )
            bump_index_version(db, doc.user_id)
        except ParseError as exc:
            _fail(db, doc, str(exc))
        except UpstreamError as exc:
            _fail(db, doc, f"{exc.message} Use Reindex once it is reachable.")
        except Exception as exc:
            log.exception("indexing failed for %s: %s", doc_id, type(exc).__name__)
            _fail(
                db,
                doc,
                "Indexing failed unexpectedly. Try Reindex, or upload the file again.",
            )
    finally:
        db.close()

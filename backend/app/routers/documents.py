"""Upload, list, reindex and delete documents."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.errors import AppError, not_found
from app.models import Document, User, utcnow
from app.schemas import DocumentOut
from app.security import get_current_user
from app.services.ingest import create_document, remove_document
from app.services.jobs import schedule_ingestion
from app.services.parsing import ALLOWED_TYPES

router = APIRouter(prefix="/documents", tags=["documents"])


def _owned(db: Session, user: User, doc_id: str) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None or doc.user_id != user.id:
        raise not_found("Document")
    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[Document]:
    """All of the user's documents, newest first."""
    stmt = select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc())
    return list(db.scalars(stmt))


@router.post("", response_model=list[DocumentOut], status_code=202)
def upload_documents(
    background: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[Document]:
    """Accept one or more files. Indexing runs in the background."""
    docs: list[Document] = []
    for upload in files:
        data = upload.file.read(settings.max_upload_bytes + 1)
        doc, queued = create_document(db, user, upload.filename or "untitled", data, settings)
        docs.append(doc)
        if queued:
            schedule_ingestion(background, doc.id)
    return docs


@router.post("/sample", response_model=list[DocumentOut])
def load_sample_documents(
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[Document]:
    """Add the bundled sample documents once per user (idempotent)."""
    folder = settings.resolve(settings.sample_docs_dir)
    files = (
        sorted(p for p in folder.iterdir() if p.suffix.lower() in ALLOWED_TYPES)
        if folder.is_dir()
        else []
    )
    if not files:
        raise AppError(404, "not_found", "Sample documents are not bundled in this build.")
    existing = {
        d.filename: d for d in db.scalars(select(Document).where(Document.user_id == user.id))
    }
    out: list[Document] = []
    for path in files:
        if path.name in existing:
            out.append(existing[path.name])
            continue
        doc, queued = create_document(db, user, path.name, path.read_bytes(), settings)
        out.append(doc)
        if queued:
            schedule_ingestion(background, doc.id)
    return out


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(
    doc_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Document:
    """One document with its indexing status."""
    return _owned(db, user, doc_id)


@router.delete("/{doc_id}", status_code=204)
def delete_document(
    doc_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Response:
    """Delete a document, its chunks and any cached answers that used it."""
    remove_document(db, _owned(db, user, doc_id))
    return Response(status_code=204)


@router.post("/{doc_id}/reindex", response_model=DocumentOut, status_code=202)
def reindex_document(
    doc_id: str,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Document:
    """Re-run ingestion from the stored original file."""
    doc = _owned(db, user, doc_id)
    if not doc.storage_path or not Path(doc.storage_path).exists():
        raise AppError(
            409,
            "conflict",
            "The original file was rejected at upload and not kept. Upload it again.",
        )
    doc.status, doc.stage, doc.error = "processing", "queued", None
    doc.progress_done = doc.progress_total = 0
    doc.updated_at = utcnow()
    db.commit()
    schedule_ingestion(background, doc.id)
    return doc

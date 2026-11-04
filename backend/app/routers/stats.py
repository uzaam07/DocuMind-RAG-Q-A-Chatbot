"""Usage and cache statistics, and the latest evaluation results."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.models import ChatSession, Document, Message, User
from app.schemas import StatsOut
from app.security import get_current_user
from app.services import cache

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    """Cache hit rates (process-wide counters) and the signed-in user's usage."""
    messages = db.scalar(
        select(func.count())
        .select_from(Message)
        .join(ChatSession, Message.session_id == ChatSession.id)
        .where(ChatSession.user_id == user.id)
    )
    return {
        "answer_cache": {
            **cache.answer_stats.snapshot(),
            "entries": cache.count_answers(db, user.id),
        },
        "embedding_cache": {
            **cache.embedding_stats.snapshot(),
            "entries": cache.count_embeddings(db),
        },
        "usage": {
            "documents": db.scalar(
                select(func.count()).select_from(Document).where(Document.user_id == user.id)
            )
            or 0,
            "sessions": db.scalar(
                select(func.count()).select_from(ChatSession).where(ChatSession.user_id == user.id)
            )
            or 0,
            "messages": messages or 0,
        },
    }


@router.get("/eval/latest")
def latest_eval(
    _: User = Depends(get_current_user), settings: Settings = Depends(get_settings)
) -> dict:
    """Latest results written by eval/run_eval.py, or {"available": false}."""
    path = settings.resolve(settings.eval_results_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"available": False}
    return {"available": True, **data}

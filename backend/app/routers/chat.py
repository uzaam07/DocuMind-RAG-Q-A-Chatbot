"""Chat sessions, message history and the ask endpoints (SSE and JSON)."""

from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import get_db, new_session
from app.errors import AppError, not_found
from app.logging_setup import get_logger
from app.models import ChatSession, Message, MessageFeedback, User, new_id, utcnow
from app.schemas import (
    AskRequest,
    AskResponse,
    FeedbackRequest,
    MessageOut,
    SessionCreate,
    SessionOut,
    SessionPatch,
)
from app.security import get_current_user
from app.services.rag import answer_events

log = get_logger(__name__)
router = APIRouter(tags=["chat"])

DEFAULT_TITLE = "New chat"
HISTORY_TURNS = 6


def _session(db: Session, user: User, session_id: str) -> ChatSession:
    chat = db.get(ChatSession, session_id)
    if chat is None or chat.user_id != user.id:
        raise not_found("Chat session")
    return chat


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[ChatSession]:
    """Chat sessions, most recently updated first."""
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    return list(db.scalars(stmt))


@router.get("/sessions/search")
def search_sessions(
    q: str = Query(min_length=1, max_length=120),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Search the authenticated user's chat titles and message bodies."""
    term = q.strip()
    if not term:
        return []
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    stmt = (
        select(ChatSession, Message)
        .outerjoin(Message, Message.session_id == ChatSession.id)
        .where(ChatSession.user_id == user.id)
        .where(
            or_(
                ChatSession.title.ilike(pattern, escape="\\"),
                Message.content.ilike(pattern, escape="\\"),
            )
        )
        .order_by(ChatSession.updated_at.desc(), Message.created_at.desc())
        .limit(limit * 4)
    )
    results: list[dict] = []
    seen: set[str] = set()
    for chat, message in db.execute(stmt):
        if chat.id in seen:
            continue
        seen.add(chat.id)
        message_matches = message and term.casefold() in message.content.casefold()
        matched = message.content if message_matches else chat.title
        index = matched.casefold().find(term.casefold())
        start = max(0, index - 72) if index >= 0 else 0
        excerpt = matched[start : start + 190]
        results.append(
            {
                "session_id": chat.id,
                "title": chat.title,
                "excerpt": excerpt,
                "matched_role": message.role if message and index >= 0 else "title",
                "updated_at": chat.updated_at,
            }
        )
        if len(results) >= limit:
            break
    return results


@router.post("/messages/{message_id}/feedback", status_code=200)
def submit_message_feedback(
    message_id: str,
    body: FeedbackRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Store a helpful/not-helpful signal for an assistant response."""
    rating = body.rating
    reason = body.reason
    message = db.get(Message, message_id)
    if message is None or message.role != "assistant":
        raise not_found("Message")
    chat = db.get(ChatSession, message.session_id)
    if chat is None or chat.user_id != user.id:
        raise not_found("Message")
    feedback = db.scalar(select(MessageFeedback).where(MessageFeedback.message_id == message_id))
    if feedback is None:
        feedback = MessageFeedback(message_id=message_id, user_id=user.id, rating=rating)
        db.add(feedback)
    elif feedback.user_id == user.id:
        feedback.rating = rating
    else:
        raise not_found("Message")
    feedback.reason = str(reason)[:500] if reason else None
    db.commit()
    return {"message_id": message_id, "rating": feedback.rating}


@router.get("/sessions/{session_id}/export")
def export_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Export a conversation as a portable Markdown transcript."""
    chat = _session(db, user, session_id)
    lines = [f"# {chat.title}", "", f"Exported: {chat.updated_at.isoformat()} UTC", ""]
    for message in chat.messages:
        label = "You" if message.role == "user" else "DocuMind"
        lines.extend([f"## {label}", "", message.content, ""])
        citations = json.loads(message.citations_json or "[]")
        for citation in citations:
            filename = citation.get("filename", "Document")
            location = citation.get("page_or_section", "Location unavailable")
            lines.append(f"> Source: {filename} — {location}")
        if citations:
            lines.append("")
    content = "\n".join(lines)
    safe = "".join(
        ch for ch in chat.title if ch.isalnum() or ch in "-_ "
    ).strip().replace(" ", "-")[:60] or "conversation"
    return {"markdown": content, "filename": f"{safe}.md"}


@router.post("/sessions", response_model=SessionOut, status_code=201)
def create_session(
    body: SessionCreate | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatSession:
    """Start a new chat."""
    title = (body.title.strip() if body and body.title else "") or DEFAULT_TITLE
    chat = ChatSession(user_id=user.id, title=title)
    db.add(chat)
    db.commit()
    return chat


@router.patch("/sessions/{session_id}", response_model=SessionOut)
def rename_session(
    session_id: str,
    body: SessionPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatSession:
    """Rename a chat."""
    chat = _session(db, user, session_id)
    chat.title = body.title
    db.commit()
    return chat


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Response:
    """Delete a chat and its messages."""
    db.delete(_session(db, user, session_id))
    db.commit()
    return Response(status_code=204)


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def list_messages(
    session_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict]:
    """Full history of a chat, oldest first, with citations and retrieval metadata."""
    chat = _session(db, user, session_id)
    feedback_rows = db.scalars(
        select(MessageFeedback).where(MessageFeedback.user_id == user.id)
    )
    feedback_by_message = {row.message_id: row.rating for row in feedback_rows}
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "citations": json.loads(m.citations_json or "[]"),
            "meta": json.loads(m.meta_json) if m.meta_json else None,
            "feedback": feedback_by_message.get(m.id),
            "created_at": m.created_at,
        }
        for m in chat.messages
    ]


def _stream_answer(session_id: str, user_id: str, body: AskRequest) -> Iterator[str]:
    """Generate SSE frames; owns its DB session because it outlives the request dependency."""
    db = new_session()
    try:
        user = db.get(User, user_id)
        chat = db.get(ChatSession, session_id)
        if user is None or chat is None:
            yield _sse("error", {"code": "not_found", "message": "Chat session was not found."})
            return
        history = [(m.role, m.content) for m in chat.messages[-HISTORY_TURNS:]]
        db.add(Message(session_id=chat.id, role="user", content=body.question))
        if chat.title == DEFAULT_TITLE:
            chat.title = body.question[:60]
        chat.updated_at = utcnow()
        db.commit()
        citations: list[dict] = []
        try:
            for ev in answer_events(db, user, body.question, body.doc_ids, body.mode, history):
                data = ev["data"]
                if ev["event"] == "done":
                    data.pop("retrieved", None)
                    msg = Message(
                        id=new_id(),
                        session_id=chat.id,
                        role="assistant",
                        content=data["answer"],
                        citations_json=json.dumps(citations, ensure_ascii=False),
                    )
                    data["message_id"] = msg.id
                    msg.meta_json = json.dumps(data, ensure_ascii=False)
                    db.add(msg)
                    chat.updated_at = utcnow()
                    db.commit()
                elif ev["event"] == "citations":
                    citations = data["citations"]
                yield _sse(ev["event"], data)
        except AppError as exc:
            yield _sse("error", {"code": exc.code, "message": exc.message})
        except Exception as exc:
            log.exception("ask failed: %s", type(exc).__name__)
            yield _sse(
                "error",
                {"code": "internal_error", "message": "Something went wrong. Try asking again."},
            )
    finally:
        db.close()


@router.post(
    "/sessions/{session_id}/ask",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "SSE stream"}},
)
def ask_in_session(
    session_id: str,
    body: AskRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Ask a question in a chat; answer streams as server-sent events."""
    _session(db, user, session_id)
    return StreamingResponse(
        _stream_answer(session_id, user.id, body),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/ask", response_model=AskResponse)
def ask_stateless(
    body: AskRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    """Ask without a session and get one JSON response (used by tests and the eval harness)."""
    citations: list[dict] = []
    done: dict = {}
    for ev in answer_events(db, user, body.question, body.doc_ids, body.mode, None):
        if ev["event"] == "citations":
            citations = ev["data"]["citations"]
        elif ev["event"] == "done":
            done = ev["data"]
    return {
        "answer": done["answer"],
        "citations": citations,
        "not_found": done["not_found"],
        "cached": done["cached"],
        "mode": done["mode"],
        "rewritten_question": done["rewritten_question"],
        "counts": done["counts"],
        "timings": done["timings"],
        "retrieved": done["retrieved"],
    }

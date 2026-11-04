"""Pydantic request and response models."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


UtcDatetime = Annotated[datetime, PlainSerializer(_iso, return_type=str)]
Mode = Literal["vector", "hybrid", "hybrid_rerank"]
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Credentials(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(min_length=8, max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL.match(v):
            raise ValueError("Enter a valid email address.")
        return v

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must be 72 bytes or fewer.")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return v.strip().lower()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    created_at: UtcDatetime


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserOut


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    file_type: str
    size_bytes: int
    status: Literal["processing", "failed", "ready"]
    stage: Literal["queued", "parsing", "chunking", "embedding", "indexing", "done"]
    progress_done: int
    progress_total: int
    chunk_count: int
    error: str | None
    created_at: UtcDatetime
    updated_at: UtcDatetime


class SessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class SessionPatch(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty.")
        return v


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    created_at: UtcDatetime
    updated_at: UtcDatetime


class Citation(BaseModel):
    id: int
    doc_id: str
    filename: str
    page_or_section: str
    snippet: str
    highlight: str | None
    score: float


class Counts(BaseModel):
    retrieved: int
    fused: int
    reranked: int
    used: int


class Timings(BaseModel):
    embed_ms: int
    retrieve_ms: int
    rerank_ms: int
    generate_ms: int
    total_ms: int


class DonePayload(BaseModel):
    message_id: str | None = None
    answer: str
    cached: bool
    mode: str
    not_found: bool
    rewritten_question: str | None
    counts: Counts
    timings: Timings


class MessageOut(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    citations: list[Citation]
    meta: DonePayload | None
    feedback: Literal["helpful", "not_helpful"] | None = None
    created_at: UtcDatetime


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    doc_ids: list[str] | None = None
    mode: Mode | None = None

    @field_validator("question")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Question cannot be empty.")
        return v


class RetrievedItem(BaseModel):
    rank: int
    doc_id: str
    filename: str
    page_or_section: str
    score: float


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    not_found: bool
    cached: bool
    mode: str
    rewritten_question: str | None
    counts: Counts
    timings: Timings
    retrieved: list[RetrievedItem]


class CacheStatsOut(BaseModel):
    hits: int
    misses: int
    hit_rate: float
    entries: int


class UsageOut(BaseModel):
    documents: int
    sessions: int
    messages: int


class StatsOut(BaseModel):
    answer_cache: CacheStatsOut
    embedding_cache: CacheStatsOut
    usage: UsageOut


class FeedbackRequest(BaseModel):
    rating: Literal["helpful", "not_helpful"]
    reason: str | None = Field(default=None, max_length=500)

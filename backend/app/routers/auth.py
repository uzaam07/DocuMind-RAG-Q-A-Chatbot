"""Registration, login and the current user."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.errors import AppError
from app.models import User
from app.schemas import Credentials, LoginRequest, TokenOut, UserOut
from app.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@lru_cache
def _dummy_hash(rounds: int) -> str:
    """A real hash to compare against when the email is unknown (keeps timing similar)."""
    return hash_password("not-a-real-password", rounds)


@router.post("/register", response_model=TokenOut, status_code=201)
def register(
    body: Credentials, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> TokenOut:
    """Create an account and return a token."""
    if db.scalar(select(User).where(User.email == body.email)):
        raise AppError(
            409, "conflict", "An account with this email already exists. Sign in instead."
        )
    user = User(
        email=body.email, password_hash=hash_password(body.password, settings.bcrypt_rounds)
    )
    db.add(user)
    db.commit()
    return TokenOut(
        access_token=create_access_token(user.id, settings), user=UserOut.model_validate(user)
    )


@router.post("/login", response_model=TokenOut)
def login(
    body: LoginRequest, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> TokenOut:
    """Exchange email and password for a token."""
    user = db.scalar(select(User).where(User.email == body.email))
    ok = verify_password(
        body.password, user.password_hash if user else _dummy_hash(settings.bcrypt_rounds)
    )
    if user is None or not ok:
        raise AppError(401, "unauthorized", "Email or password is incorrect.")
    return TokenOut(
        access_token=create_access_token(user.id, settings), user=UserOut.model_validate(user)
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    """Return the signed-in user."""
    return user

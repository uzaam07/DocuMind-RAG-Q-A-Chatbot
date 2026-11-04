"""Password hashing, JWT issuing and the current-user dependency."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.errors import AppError
from app.models import User

_bearer = HTTPBearer(auto_error=False)
_ALGORITHM = "HS256"


def hash_password(password: str, rounds: int) -> str:
    """Return a bcrypt hash for the password."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a password against its bcrypt hash without raising on bad input."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


def create_access_token(user_id: str, settings: Settings) -> str:
    """Issue a signed JWT for the user."""
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_token(token: str, settings: Settings) -> str:
    """Return the user id inside a valid token or raise an unauthorized error."""
    try:
        data = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise AppError(401, "unauthorized", "Your session has expired. Sign in again.") from exc
    except jwt.InvalidTokenError as exc:
        raise AppError(
            401, "unauthorized", "Your sign-in token is not valid. Sign in again."
        ) from exc
    sub = data.get("sub")
    if not isinstance(sub, str):
        raise AppError(401, "unauthorized", "Your sign-in token is not valid. Sign in again.")
    return sub


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """FastAPI dependency: resolve the bearer token to a User row."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise AppError(401, "unauthorized", "Sign in to continue.")
    user = db.get(User, decode_token(creds.credentials, settings))
    if user is None:
        raise AppError(401, "unauthorized", "This account no longer exists. Sign in again.")
    return user

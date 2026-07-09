"""JWT authentication and bcrypt password hashing for FastAPI."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.backend import database as db

logger = logging.getLogger(__name__)

_ALGO = "HS256"  # symmetric — the configured value is a shared SECRET, not a keypair
_TTL_HOURS = 24
_ENV = os.getenv("APP_ENV", "development").lower()

# F-05 fix: never sign with a hard-coded default in a real environment.
# Accept JWT_SECRET (preferred for HS256) or legacy JWT_PRIVATE_KEY.
_SECRET = os.getenv("JWT_SECRET") or os.getenv("JWT_PRIVATE_KEY")
if not _SECRET:
    if _ENV in ("production", "staging", "prod"):
        raise RuntimeError(
            "JWT_SECRET (or JWT_PRIVATE_KEY) must be set in production/staging. "
            "Refusing to start with a default signing key (token-forgery risk)."
        )
    _SECRET = "dev-only-insecure-key-not-for-deployment"
    logger.warning(
        "JWT secret not set; using an insecure development-only key (APP_ENV=%s). "
        "Set JWT_SECRET before any non-dev deployment.",
        _ENV,
    )

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=_TTL_HOURS),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGO)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _SECRET, algorithms=[_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired — please log in again")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    payload = decode_token(credentials.credentials)
    user = db.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User account not found")
    return user

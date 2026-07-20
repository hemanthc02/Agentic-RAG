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
_ENV = os.getenv("APP_ENV", "development").lower()
# Token lifetime honours JWT_ACCESS_TTL_SECONDS (default 24h) instead of a
# hard-coded constant, so a deployment can shrink the replay window.
_TTL_SECONDS = int(os.getenv("JWT_ACCESS_TTL_SECONDS", str(24 * 3600)))

# Known placeholder / example secrets that must NEVER be accepted as a real
# signing key — anyone reading the repo or a copied .env could forge tokens.
_PLACEHOLDER_SECRETS = {
    "dev-only-insecure-key-not-for-deployment",
    "dummy-jwt-private-key-replace-me-with-real-rsa-or-ec-key",
    "changeme", "secret", "your-secret-key", "",
}

# F-05 fix: never sign with a hard-coded default in a real environment.
# Accept JWT_SECRET (preferred for HS256) or legacy JWT_PRIVATE_KEY.
_SECRET = (os.getenv("JWT_SECRET") or os.getenv("JWT_PRIVATE_KEY") or "").strip()
_is_prod = _ENV in ("production", "staging", "prod")
if _SECRET in _PLACEHOLDER_SECRETS:
    if _is_prod:
        raise RuntimeError(
            "JWT_SECRET is unset or a known placeholder. Refusing to start with a "
            "forgeable signing key. Set a random 256-bit JWT_SECRET."
        )
    _SECRET = "dev-only-insecure-key-not-for-deployment"
    logger.warning(
        "JWT secret is a placeholder; using an insecure DEV-ONLY key (APP_ENV=%s). "
        "Tokens are forgeable — set a random JWT_SECRET before sharing or deploying.",
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
        "exp": datetime.utcnow() + timedelta(seconds=_TTL_SECONDS),
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

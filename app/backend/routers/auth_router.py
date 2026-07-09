"""Authentication endpoints: register, login, me."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from app.backend import auth, database as db

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── In-memory sliding-window rate limiter (per IP) ─────────────────────────

_login_attempts: dict[str, list[float]] = defaultdict(list)
_WINDOW_SECONDS = 60
_MAX_ATTEMPTS = 10  # 10 attempts per minute per IP


def _check_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    attempts = _login_attempts[ip]
    # Drop attempts outside the window
    _login_attempts[ip] = [t for t in attempts if now - t < _WINDOW_SECONDS]
    if len(_login_attempts[ip]) >= _MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail=f"Too many attempts from this address. Try again in {_WINDOW_SECONDS}s.",
            headers={"Retry-After": str(_WINDOW_SECONDS)},
        )
    _login_attempts[ip].append(now)


# ── Request / Response models ──────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=80)
    password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
    settings: dict  # Return saved mode/provider so frontend can sync immediately


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
def register(req: RegisterRequest, request: Request):
    _check_rate_limit(request)
    if db.get_user_by_email(req.email):
        raise HTTPException(status_code=409, detail="Email already registered")
    hashed = auth.hash_password(req.password)
    user = db.create_user(req.email, req.name, hashed)
    db.create_corpus(user["id"], "My Documents")
    token = auth.create_token(user["id"], user["email"])
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    settings = db.get_user_settings(user["id"])
    settings.pop("groq_api_key", None)  # never send raw key
    return {"access_token": token, "token_type": "bearer", "user": safe_user, "settings": settings}


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request):
    _check_rate_limit(request)
    user = db.get_user_by_email(req.email)
    if not user or not auth.verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = auth.create_token(user["id"], user["email"])
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    settings = db.get_user_settings(user["id"])
    settings.pop("groq_api_key", None)
    return {"access_token": token, "token_type": "bearer", "user": safe_user, "settings": settings}


@router.get("/me")
def me(current_user: Annotated[dict, Depends(auth.get_current_user)]):
    return {k: v for k, v in current_user.items() if k != "password_hash"}

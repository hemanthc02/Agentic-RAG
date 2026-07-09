"""Conversations & messages — persistent chat history."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.backend import auth
from app.backend import database as db

router = APIRouter(prefix="/api", tags=["conversations"])


class CreateConvRequest(BaseModel):
    title: str = Field(default="New conversation", max_length=200)
    corpus_id: str | None = None
    mode: str = "rag"  # "rag" | "guide" | "viva"


class RenameConvRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


class AddMessageRequest(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)
    query_id: str | None = None
    metadata: dict = {}


# ── Conversations ────────────────────────────────────────────────────────────

@router.get("/conversations")
def list_conversations(
    user: Annotated[dict, Depends(auth.get_current_user)],
    limit: int = 50,
):
    return db.list_conversations(user["id"], limit=min(limit, 100))


@router.post("/conversations")
def create_conversation(
    req: CreateConvRequest,
    user: Annotated[dict, Depends(auth.get_current_user)],
):
    return db.create_conversation(
        user_id=user["id"],
        corpus_id=req.corpus_id,
        title=req.title,
        mode=req.mode,
    )


@router.get("/conversations/{conv_id}")
def get_conversation(
    conv_id: str,
    user: Annotated[dict, Depends(auth.get_current_user)],
):
    conv = db.get_conversation(conv_id, user["id"])
    if not conv:
        raise HTTPException(404, "Conversation not found")
    messages = db.list_messages(conv_id)
    return {**conv, "messages": messages}


@router.patch("/conversations/{conv_id}")
def rename_conversation(
    conv_id: str,
    req: RenameConvRequest,
    user: Annotated[dict, Depends(auth.get_current_user)],
):
    ok = db.update_conversation_title(conv_id, user["id"], req.title)
    if not ok:
        raise HTTPException(404, "Conversation not found")
    return {"ok": True}


@router.delete("/conversations/{conv_id}")
def delete_conversation(
    conv_id: str,
    user: Annotated[dict, Depends(auth.get_current_user)],
):
    ok = db.delete_conversation(conv_id, user["id"])
    if not ok:
        raise HTTPException(404, "Conversation not found")
    return {"ok": True}


# ── Messages ─────────────────────────────────────────────────────────────────

@router.get("/conversations/{conv_id}/messages")
def get_messages(
    conv_id: str,
    user: Annotated[dict, Depends(auth.get_current_user)],
):
    if not db.get_conversation(conv_id, user["id"]):
        raise HTTPException(404, "Conversation not found")
    return db.list_messages(conv_id)


@router.post("/conversations/{conv_id}/messages")
def add_message(
    conv_id: str,
    req: AddMessageRequest,
    user: Annotated[dict, Depends(auth.get_current_user)],
):
    if not db.get_conversation(conv_id, user["id"]):
        raise HTTPException(404, "Conversation not found")
    msg = db.add_message(conv_id, req.role, req.content, req.query_id, req.metadata)
    db.touch_conversation(conv_id)
    return msg

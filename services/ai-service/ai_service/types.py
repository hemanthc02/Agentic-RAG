"""Provider-agnostic value objects for the LLM layer.

These types are the contract every provider speaks, so agents and the RAG
pipeline never depend on a vendor SDK's shapes.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Role(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"


class Message(BaseModel):
    role: Role
    content: str


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class Completion(BaseModel):
    """A non-streaming generation result, normalised across providers."""

    text: str
    provider: str
    model: str
    usage: Usage = Field(default_factory=Usage)
    finish_reason: str | None = None
    latency_ms: int | None = None


class GenerationParams(BaseModel):
    temperature: float = 0.0
    max_tokens: int = 1024
    top_p: float = 1.0
    stop: list[str] | None = None

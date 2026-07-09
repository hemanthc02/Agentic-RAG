"""ai-service: a provider-agnostic LLM layer for VeritasRAG.

Public surface:
    from ai_service import LLMProviderFactory, LLMProvider, Message, Role
"""

from ai_service.base import LLMProvider, LLMError
from ai_service.factory import LLMProviderFactory
from ai_service.types import Completion, GenerationParams, Message, Role, Usage

__all__ = [
    "LLMProviderFactory",
    "LLMProvider",
    "LLMError",
    "Message",
    "Role",
    "Completion",
    "Usage",
    "GenerationParams",
]

__version__ = "0.1.0"

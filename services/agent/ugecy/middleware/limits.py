"""Resilience middleware: retry and model fallback. No call or run caps (operator decision)."""
from __future__ import annotations

from langchain.agents.middleware import (
    ModelFallbackMiddleware,
    ModelRetryMiddleware,
)
from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.language_models import BaseChatModel

from ugecy.settings import Settings


def limit_middleware(settings: Settings, fallback: BaseChatModel, run_limit: int | None = None) -> list[AgentMiddleware]:
    return [
        ModelRetryMiddleware(max_retries=2, backoff_factor=2.0),
        ModelFallbackMiddleware(fallback),
    ]

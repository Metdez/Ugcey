"""Run-cost guards from langchain (verified present in 1.4.9): call cap, retry, model fallback."""
from __future__ import annotations

from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ModelFallbackMiddleware,
    ModelRetryMiddleware,
)
from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.language_models import BaseChatModel

from ugecy.settings import Settings


def limit_middleware(settings: Settings, fallback: BaseChatModel) -> list[AgentMiddleware]:
    return [
        ModelCallLimitMiddleware(run_limit=settings.max_model_calls_per_run, exit_behavior="end"),
        ModelRetryMiddleware(max_retries=2, backoff_factor=2.0),
        ModelFallbackMiddleware(fallback),
    ]

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


def limit_middleware(settings: Settings, fallback: BaseChatModel, run_limit: int | None = None,
                     capped: bool = True) -> list[AgentMiddleware]:
    """capped=False drops the model-call cap (retry and fallback stay)."""
    cap = [ModelCallLimitMiddleware(run_limit=run_limit or settings.max_model_calls_per_run, exit_behavior="end")] if capped else []
    return [*cap, ModelRetryMiddleware(max_retries=2, backoff_factor=2.0), ModelFallbackMiddleware(fallback)]

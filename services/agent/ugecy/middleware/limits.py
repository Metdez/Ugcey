"""Resilience middleware: retry and model fallback. No call or run caps (operator decision)."""
from __future__ import annotations

from langchain.agents.middleware import (
    ModelFallbackMiddleware,
    ModelRetryMiddleware,
)
from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.language_models import BaseChatModel

from ugecy.settings import Settings

# LangGraph requires a number here; this one is never reached (one count per graph step).
RECURSION_LIMIT = 1_000_000_000


def limit_middleware(settings: Settings, fallback: BaseChatModel) -> list[AgentMiddleware]:
    return [
        ModelRetryMiddleware(max_retries=2, backoff_factor=2.0),
        ModelFallbackMiddleware(fallback),
    ]


def lift_subagent_recursion_limit() -> None:
    """LangChain's create_agent binds every agent to recursion_limit 9_999, and a subagent's bound limit beats the
    run's (deepagents#3634), so a long subagent stopped the whole run mid-way (~2,500 model calls). deepagents has
    no option for it, so re-bind each subagent it compiles. test_graph_build pins this across library upgrades."""
    from deepagents.middleware import subagents

    make = subagents.create_sub_agent
    if getattr(make, "ugecy_unbounded", False):
        return

    def create_sub_agent(*args, **kwargs):
        return make(*args, **kwargs).with_config({"recursion_limit": RECURSION_LIMIT})

    create_sub_agent.ugecy_unbounded = True  # type: ignore[attr-defined]
    subagents.create_sub_agent = create_sub_agent

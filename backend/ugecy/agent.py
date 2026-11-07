"""Ugecy research agent built on LangChain Deep Agents."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

from deepagents import create_deep_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from ugecy.tools import firecrawl_tools

RESEARCH_PROMPT = """You are Ugecy's research analyst for compliant UGC campaigns.
Use the Firecrawl tools to gather current, public, permitted sources: search to find them,
map to explore a site, scrape to read a page. For every claim you rely on, record the URL,
its retrieval date, and any licensing or usage limits. Turn findings into original,
explainable recommendations; never copy scripts or creative work."""


def resolve_model(model: str | BaseChatModel | None = None) -> str | BaseChatModel:
    """Pick the chat model from the argument or UGECY_MODEL, refusing Anthropic models."""
    chosen = model or os.environ.get("UGECY_MODEL")
    if not chosen:
        raise RuntimeError("No model configured: set UGECY_MODEL (provider:model).")
    name = chosen if isinstance(chosen, str) else type(chosen).__module__
    if "anthropic" in name.lower() or "claude" in name.lower():
        raise ValueError("Anthropic models are not allowed in Ugecy; choose another provider.")
    return chosen


def build_agent(
    model: str | BaseChatModel | None = None,
    extra_tools: Sequence[BaseTool] = (),
    **kwargs: Any,
):
    """Create the research Deep Agent with the Firecrawl tools plus any extra tools."""
    return create_deep_agent(
        model=resolve_model(model),
        tools=[*firecrawl_tools(), *extra_tools],
        system_prompt=kwargs.pop("system_prompt", RESEARCH_PROMPT),
        **kwargs,
    )

"""Per-role model routing. Roles map to Settings.model_<role>; no Anthropic models."""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from ugecy.llm.workers_ai import make_model
from ugecy.settings import Settings

ROLES = ("orchestrator", "research", "creative", "critic", "fast", "vision", "fallback")


def models_for(settings: Settings) -> dict[str, BaseChatModel]:
    return {role: make_model(role, settings) for role in ROLES}

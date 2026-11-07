"""Deep Agents memory wiring for every agent.

- LiveMemoryMiddleware: deepagents' MemoryMiddleware that reloads its sources on every agent invocation. The stock
  one loads once per thread, so it would miss lessons written earlier in the same thread.
- ExperienceMiddleware: after each subagent task or orchestrator turn, records the episode and merges lessons in
  the background (ugecy.memory.experience).
"""
from __future__ import annotations

import logging
from typing import Any

from deepagents.middleware.memory import MemoryMiddleware
from langchain.agents.middleware.types import AgentMiddleware

from ugecy.memory import experience

log = logging.getLogger(__name__)
SHARED_MEMORY = "/memories/AGENTS.md"


def agent_memory_path(agent: str) -> str:
    return f"/memories/agents/{agent}.md"


def memory_sources(agent: str) -> list[str]:
    return [SHARED_MEMORY, agent_memory_path(agent)]


class LiveMemoryMiddleware(MemoryMiddleware):
    name = "LiveMemoryMiddleware"

    def before_agent(self, state, runtime, config):  # type: ignore[override]
        return super().before_agent({k: v for k, v in state.items() if k != "memory_contents"}, runtime, config)

    async def abefore_agent(self, state, runtime, config):  # type: ignore[override]
        return await super().abefore_agent({k: v for k, v in state.items() if k != "memory_contents"}, runtime, config)


class ExperienceMiddleware(AgentMiddleware):
    name = "ExperienceMiddleware"

    def __init__(self, agent: str, store: Any, model: Any | None, workspace_id: str = "default") -> None:
        super().__init__()
        self.agent, self.store, self.model, self.workspace_id = agent, store, model, workspace_id

    async def aafter_agent(self, state, runtime):
        stuck = experience.take_stuck()
        if self.store is None:
            return
        try:
            ep = experience.episode_from(list(state.get("messages") or []), self.agent, stuck)
            if ep is not None:
                ws = getattr(getattr(runtime, "context", None), "workspace_id", None) or self.workspace_id
                experience.schedule(self.store, ws, ep, self.model)
        except Exception:
            log.warning("experience capture failed for %s", self.agent, exc_info=True)
        return

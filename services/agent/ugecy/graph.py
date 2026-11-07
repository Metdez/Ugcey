"""The Deep Agents graph: orchestrator + registered subagents, middleware, backends, permissions."""
from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from deepagents.backends.utils import create_file_data
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.language_models import BaseChatModel

from ugecy import registry
from ugecy.agents._base import load_prompt
from ugecy.deps import Deps
from ugecy.interfaces import SKILLS_NS, memories_ns
from ugecy.llm.routing import models_for
from ugecy.middleware.audit import AuditMiddleware
from ugecy.middleware.compat import CompatMiddleware
from ugecy.middleware.limits import limit_middleware
from ugecy.middleware.memory import (
    ExperienceMiddleware,
    LiveMemoryMiddleware,
    agent_memory_path,
    memory_sources,
)
from ugecy.middleware.stop import StopMiddleware
from ugecy.middleware.stuck import LOOKUP_TOOLS, StuckMiddleware

GENERAL_PURPOSE_PROMPT = (
    "You are a read-only helper. Search, read and summarize files in the virtual filesystem and return "
    "a concise answer. You have no external tools and must not claim to have performed external actions."
)

ORCHESTRATOR = "orchestrator"


def memory_footer(agent: str, has_lookup: bool = True) -> str:
    look = ("`web_search` (Firecrawl) for how to do it, `fetch_page` for the best result" if has_lookup else
            "delegate a `web_search` lookup to research-analyst (Firecrawl), or hand the step to a different specialist")
    return (f"## Memory and getting unstuck\n"
            f"- `{agent_memory_path(agent)}` holds lessons from your earlier runs (loaded above as agent memory). "
            "Use them before acting: they record what worked and what failed.\n"
            "- Your runs are recorded and merged into those lessons automatically. When you work out a reusable "
            f"how-to (a navigation path, a tool quirk, a fix), also add it right away with `edit_file` on "
            f"`{agent_memory_path(agent)}` as one short '- ' line. Never save passwords, codes, keys or personal data.\n"
            "- If you keep repeating an action, keep getting errors, or the screen does not change, stop and look it "
            f"up: {look}, then change approach.")


@dataclass
class RunContext:
    """Immutable per-run context: agent.astream(..., context=RunContext(workspace_id=...))."""
    workspace_id: str = "default"


def _middleware(deps: Deps, models: dict[str, BaseChatModel], run_limit: int | None = None) -> list[Any]:
    return [StopMiddleware(), AuditMiddleware(), *limit_middleware(deps.settings, models["fallback"], run_limit),
            CompatMiddleware()]


def _memory_middleware(deps: Deps, models: dict[str, BaseChatModel], backend: Any, agent: str,
                       has_lookup: bool) -> list[Any]:
    """Per-agent Deep Agents memory (shared AGENTS.md + own lessons), automatic recording, stuck recovery."""
    return [LiveMemoryMiddleware(backend=backend, sources=memory_sources(agent)),
            ExperienceMiddleware(agent, deps.store, models["fast"], deps.settings.workspace_id),
            StuckMiddleware(has_lookup=has_lookup)]


def _subagents(deps: Deps, models: dict[str, BaseChatModel], backend: Any = None) -> list[dict[str, Any]]:
    s = deps.settings
    backend = backend or _backend()
    specs: list[dict[str, Any]] = [{
        "name": "general-purpose",
        "description": "Read-only helper for searching and summarizing files. Has no external tools.",
        "system_prompt": GENERAL_PURPOSE_PROMPT, "tools": [], "model": models["fast"],
        "middleware": _middleware(deps, models, s.max_model_calls_per_subagent), "skills": ["/skills/"],
    }]
    for agent in registry.enabled_agents(s.disabled("agents")):
        tools = registry.tools_for(agent, s.disabled("tools"))  # always explicit: no inherited tools
        has_lookup = bool(LOOKUP_TOOLS & {t.name for t in tools})
        spec: dict[str, Any] = {
            "name": agent.name, "description": agent.description, "tools": tools,
            "system_prompt": f"{agent.system_prompt}\n\n{memory_footer(agent.name, has_lookup)}",
            "model": models.get(agent.model_role, models["fast"]),
            "middleware": [*_middleware(deps, models, s.max_model_calls_per_subagent),
                           *_memory_middleware(deps, models, backend, agent.name, has_lookup)],
        }
        if agent.skills:
            spec["skills"] = agent.skills
        specs.append(spec)
    return specs


def _system_prompt(deps: Deps) -> str:
    m = deps.modes
    line = (f"Current provider modes: llm={m.llm}, research={m.research}, media={m.media}, "
            f"device=dynamic (call device_status), publishing={m.publishing}.")
    return f"{load_prompt('orchestrator')}\n\n{memory_footer(ORCHESTRATOR, has_lookup=False)}\n\n{line}"


def _backend() -> CompositeBackend:
    return CompositeBackend(default=StateBackend(), routes={
        "/memories/": StoreBackend(namespace=lambda rt: memories_ns(rt.context.workspace_id)),
        "/skills/": StoreBackend(namespace=lambda rt: SKILLS_NS),
    })


def build_agent(deps: Deps, models: dict[str, BaseChatModel] | None = None):
    models = models or models_for(deps.settings)
    backend = _backend()
    permissions: list = []  # no filesystem gates (operator decision)
    agent = create_deep_agent(
        model=models["orchestrator"], name="ugecy-orchestrator", tools=[], context_schema=RunContext,
        system_prompt=_system_prompt(deps), subagents=_subagents(deps, models, backend),
        middleware=[TodoListMiddleware(), *_middleware(deps, models),
                    *_memory_middleware(deps, models, backend, ORCHESTRATOR, has_lookup=False)],
        backend=backend, permissions=permissions, interrupt_on=registry.interrupt_map(),
        skills=["/skills/"],  # memory: LiveMemoryMiddleware above (reloads every turn, per-agent lessons)
        checkpointer=deps.checkpointer, store=deps.store,
    )
    return agent.with_config({"recursion_limit": 100_000})


async def seed_store(store: Any, workspace_id: str) -> None:
    """Write the playbooks (always refreshed) and the brand-voice template (only if missing)."""
    root = files("ugecy").joinpath("skills")
    for entry in root.iterdir():
        skill = entry.joinpath("SKILL.md")
        if entry.is_dir() and not entry.name.startswith("_") and skill.is_file():
            await store.aput(SKILLS_NS, f"/{entry.name}/SKILL.md", create_file_data(skill.read_text("utf-8")))
    if await store.aget(memories_ns(workspace_id), "/AGENTS.md") is None:
        template = root.joinpath("_memory", "AGENTS.md").read_text("utf-8")
        await store.aput(memories_ns(workspace_id), "/AGENTS.md", create_file_data(template))

"""The Deep Agents graph: orchestrator + registered subagents, middleware, backends, permissions."""
from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from deepagents import FilesystemPermission, create_deep_agent
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

GENERAL_PURPOSE_PROMPT = (
    "You are a read-only helper. Search, read and summarize files in the virtual filesystem and return "
    "a concise answer. You have no external tools and must not claim to have performed external actions."
)


@dataclass
class RunContext:
    """Immutable per-run context: agent.astream(..., context=RunContext(workspace_id=...))."""
    workspace_id: str = "default"


def _middleware(deps: Deps, models: dict[str, BaseChatModel], run_limit: int | None = None) -> list[Any]:
    return [AuditMiddleware(), *limit_middleware(deps.settings, models["fallback"], run_limit), CompatMiddleware()]


def _subagents(deps: Deps, models: dict[str, BaseChatModel]) -> list[dict[str, Any]]:
    s = deps.settings
    specs: list[dict[str, Any]] = [{
        "name": "general-purpose",
        "description": "Read-only helper for searching and summarizing files. Has no external tools.",
        "system_prompt": GENERAL_PURPOSE_PROMPT, "tools": [], "model": models["fast"],
        "middleware": _middleware(deps, models, s.max_model_calls_per_subagent), "skills": ["/skills/"],
    }]
    for agent in registry.enabled_agents(s.disabled("agents")):
        spec: dict[str, Any] = {
            "name": agent.name, "description": agent.description, "system_prompt": agent.system_prompt,
            "tools": registry.tools_for(agent, s.disabled("tools")),  # always explicit: no inherited tools
            "model": models.get(agent.model_role, models["fast"]),
            "middleware": _middleware(deps, models, s.max_model_calls_per_subagent),
        }
        if agent.skills:
            spec["skills"] = agent.skills
        specs.append(spec)
    return specs


def _system_prompt(deps: Deps) -> str:
    m = deps.modes
    line = (f"Current provider modes: llm={m.llm}, research={m.research}, media={m.media}, "
            f"device={m.device}, publishing={m.publishing}.")
    return f"{load_prompt('orchestrator')}\n\n{line}"


def build_agent(deps: Deps, models: dict[str, BaseChatModel] | None = None):
    models = models or models_for(deps.settings)
    backend = CompositeBackend(default=StateBackend(), routes={
        "/memories/": StoreBackend(namespace=lambda rt: memories_ns(rt.context.workspace_id)),
        "/skills/": StoreBackend(namespace=lambda rt: SKILLS_NS),
    })
    permissions = [
        FilesystemPermission(operations=["write"], paths=["/skills/**"], mode="deny"),
        FilesystemPermission(operations=["write"], paths=["/memories/**"], mode="interrupt"),
    ]
    agent = create_deep_agent(
        model=models["orchestrator"], name="ugecy-orchestrator", tools=[], context_schema=RunContext,
        system_prompt=_system_prompt(deps), subagents=_subagents(deps, models),
        middleware=[TodoListMiddleware(), *_middleware(deps, models)],
        backend=backend, permissions=permissions, interrupt_on=registry.interrupt_map(),
        skills=["/skills/"], memory=["/memories/AGENTS.md"],
        checkpointer=deps.checkpointer, store=deps.store,
    )
    return agent.with_config({"recursion_limit": 400})


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

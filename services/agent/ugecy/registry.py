"""Module registry: tools and subagents register themselves at import time.

Slot a feature in or out by adding/removing its import path in ugecy/modules.py or by
setting UGECY_DISABLED_AGENTS / UGECY_DISABLED_TOOLS (comma-separated names).
The graph builder (ugecy/graph.py) reads only from here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import BaseTool

# InterruptOnConfig shape (langchain HumanInTheLoopMiddleware):
#   {"allowed_decisions": ["approve", "edit", "reject"], "description": "..."}
APPROVE_EDIT_REJECT: dict[str, Any] = {"allowed_decisions": ["approve", "edit", "reject"]}
APPROVE_REJECT: dict[str, Any] = {"allowed_decisions": ["approve", "reject"]}


@dataclass
class ToolSpec:
    tool: BaseTool
    domain: str  # "research" | "media" | "publishing" | "device" | "analytics" | "memory" | "creative"
    interrupt: dict[str, Any] | bool | None = None  # None/False = no approval needed
    side_effect: bool = False  # True if it changes anything outside the agent's own files


@dataclass
class AgentModule:
    name: str  # kebab-case, e.g. "research-analyst"
    description: str  # routing signal for the orchestrator's `task` tool
    system_prompt: str
    tools: list[str] = field(default_factory=list)  # names in TOOLS
    model_role: str = "fast"  # key in settings model routing: orchestrator|research|creative|critic|fast|vision
    skills: list[str] = field(default_factory=list)  # backend paths, e.g. ["/skills/"]
    enabled: bool = True
    long_running: bool = False  # higher model-call cap (settings.max_model_calls_research); still stops cleanly


TOOLS: dict[str, ToolSpec] = {}
AGENTS: dict[str, AgentModule] = {}


def register_tool(tool: BaseTool, *, domain: str, interrupt: dict[str, Any] | bool | None = None,
                  side_effect: bool = False) -> BaseTool:
    if tool.name in TOOLS:
        raise ValueError(f"duplicate tool name: {tool.name}")
    TOOLS[tool.name] = ToolSpec(tool=tool, domain=domain, interrupt=interrupt, side_effect=side_effect)
    return tool


def register_agent(module: AgentModule) -> AgentModule:
    if module.name in AGENTS:
        raise ValueError(f"duplicate agent name: {module.name}")
    AGENTS[module.name] = module
    return module


def enabled_agents(disabled: set[str]) -> list[AgentModule]:
    return [a for a in AGENTS.values() if a.enabled and a.name not in disabled]


def tools_for(agent: AgentModule, disabled_tools: set[str]) -> list[BaseTool]:
    missing = [t for t in agent.tools if t not in TOOLS]
    if missing:
        raise KeyError(f"agent {agent.name} references unknown tools: {missing}")
    return [TOOLS[t].tool for t in agent.tools if t not in disabled_tools]


def interrupt_map() -> dict[str, Any]:
    """interrupt_on for create_deep_agent: every registered tool that needs approval."""
    return {name: spec.interrupt for name, spec in TOOLS.items() if spec.interrupt}

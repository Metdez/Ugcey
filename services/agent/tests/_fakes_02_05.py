"""Fakes for the graph/llm tests (plan 02-05)."""
from __future__ import annotations

import importlib
from types import SimpleNamespace

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from ugecy import registry
from ugecy.contracts import ProviderModes
from ugecy.settings import Settings

AGENT_MODULES = ["research", "creative", "critic", "production", "publishing", "device", "analytics"]
SIDE_EFFECT = {"generate_media": "media", "publish_post": "publishing", "device_commit": "device",
               "device_tap": "device", "device_swipe": "device", "device_type": "device",
               "device_start_session": "device"}


class FakeChat(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):  # the scripted replies already carry any tool calls
        return self


def fake_model(*replies: AIMessage | str) -> FakeChat:
    return FakeChat(messages=iter([AIMessage(content=r) if isinstance(r, str) else r for r in replies]))


def fake_tool(name: str) -> StructuredTool:
    return StructuredTool.from_function(lambda **_: "ok", name=name, description=f"fake {name}",
                                        args_schema={"type": "object", "properties": {}})


def install_registry(monkeypatch) -> None:
    """Empty registry, re-register the seven real agent modules, add fake tools they reference."""
    mods = [importlib.import_module(f"ugecy.agents.{m}") for m in AGENT_MODULES]  # first import may register
    monkeypatch.setattr(registry, "TOOLS", {})
    monkeypatch.setattr(registry, "AGENTS", {})
    for mod in mods:
        importlib.reload(mod)
    for agent in registry.AGENTS.values():
        for tool in agent.tools:
            if tool not in registry.TOOLS:
                registry.register_tool(
                    fake_tool(tool), domain=SIDE_EFFECT.get(tool, "research"), side_effect=tool in SIDE_EFFECT,
                    interrupt=registry.APPROVE_EDIT_REJECT if tool == "generate_media" else None)


class FakeApp:
    def __init__(self, fail: bool = False) -> None:
        self.entries, self.fail = [], fail

    async def add_audit(self, entry) -> None:
        if self.fail:
            raise RuntimeError("db down")
        self.entries.append(entry)


def fake_deps(app: FakeApp | None = None) -> SimpleNamespace:
    return SimpleNamespace(settings=Settings(internal_mode="test"), modes=ProviderModes(media="live"),
                           app=app or FakeApp(), checkpointer=InMemorySaver(), store=InMemoryStore())


def fake_models(orchestrator: FakeChat | None = None) -> dict:
    models = {r: fake_model("done") for r in ("research", "creative", "critic", "fast", "vision", "fallback")}
    models["orchestrator"] = orchestrator or fake_model("done")
    return models

"""Fakes for the 02-04 API/stream tests: scripted chat model, in-memory AppStore, fake Deps."""
from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from ugecy.contracts import (
    ApprovalRecord,
    Asset,
    AuditEntry,
    ConnectedAccount,
    Post,
    Source,
    ThreadSummary,
)


class ScriptedModel(BaseChatModel):
    """Returns the scripted AIMessages in order (last one repeats). Streams text word by word."""

    script: list[AIMessage]
    cursor: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> ScriptedModel:
        return self

    def _next(self) -> AIMessage:
        msg = self.script[min(self.cursor, len(self.script) - 1)]
        self.cursor += 1
        return msg

    def _generate(self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None,
                  **kwargs: Any) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next())])

    def _stream(self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None,
                **kwargs: Any) -> Iterator[ChatGenerationChunk]:
        msg = self._next()
        text = msg.content if isinstance(msg.content, str) else ""
        words = text.split(" ") if text else []
        for i, w in enumerate(words):
            yield ChatGenerationChunk(message=AIMessageChunk(content=w + (" " if i < len(words) - 1 else ""),
                                                             id=msg.id))
        yield ChatGenerationChunk(message=AIMessageChunk(
            content="", id=msg.id, additional_kwargs=msg.additional_kwargs,
            tool_call_chunks=[{"name": tc["name"], "args": __import__("json").dumps(tc["args"]),
                               "id": tc["id"], "index": i} for i, tc in enumerate(msg.tool_calls)]))

    async def _astream(self, *a: Any, **kw: Any) -> AsyncIterator[ChatGenerationChunk]:
        for chunk in self._stream(*a, **kw):
            yield chunk


class MemAppStore:
    """Minimal in-memory AppStore."""

    def __init__(self) -> None:
        self.threads: dict[str, ThreadSummary] = {}
        self.audit: list[AuditEntry] = []
        self.approvals: dict[str, ApprovalRecord] = {}
        self.sources: dict[str, list[Source]] = {}
        self.accounts: dict[str, ConnectedAccount] = {}
        self.assets: dict[str, Asset] = {}
        self.posts: dict[str, Post] = {}

    async def init(self) -> None: ...
    async def upsert_thread(self, thread: ThreadSummary) -> None: self.threads[thread.id] = thread
    async def get_thread(self, thread_id: str): return self.threads.get(thread_id)
    async def list_threads(self): return list(self.threads.values())
    async def delete_thread(self, thread_id: str) -> None: self.threads.pop(thread_id, None)
    async def add_audit(self, entry: AuditEntry) -> None: self.audit.append(entry)

    async def list_audit(self, thread_id: str | None = None, limit: int = 100):
        return [a for a in self.audit if thread_id in (None, a.thread_id)][:limit]

    async def upsert_asset(self, asset: Asset) -> None: self.assets[asset.id] = asset
    async def get_asset(self, asset_id: str): return self.assets.get(asset_id)

    async def list_assets(self, thread_id: str | None = None):
        return [a for a in self.assets.values() if thread_id in (None, a.thread_id)]

    async def upsert_post(self, post: Post) -> None: self.posts[post.id] = post
    async def get_post(self, post_id: str): return self.posts.get(post_id)

    async def list_posts(self, thread_id: str | None = None):
        return [p for p in self.posts.values() if thread_id in (None, p.thread_id)]

    async def upsert_account(self, account: ConnectedAccount) -> None: self.accounts[account.id] = account
    async def list_accounts(self): return list(self.accounts.values())
    async def upsert_approval(self, record: ApprovalRecord) -> None: self.approvals[record.interrupt_id] = record
    async def get_approval(self, interrupt_id: str): return self.approvals.get(interrupt_id)

    async def list_approvals(self, status: str | None = None):
        return [a for a in self.approvals.values() if status in (None, a.status)]

    async def add_source(self, thread_id: str, source: Source) -> None:
        lst = self.sources.setdefault(thread_id, [])
        if all(s.url != source.url for s in lst):
            lst.append(source)

    async def list_sources(self, thread_id: str): return list(self.sources.get(thread_id, []))


# ---- app wiring helpers --------------------------------------------------------------------
import json
import sys
import types
from dataclasses import dataclass

import httpx
from deepagents import create_deep_agent
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from ugecy.contracts import DeviceInfo, ProviderModes
from ugecy.deps import Deps
from ugecy.main import create_app
from ugecy.settings import Settings


@dataclass
class Ctx:
    workspace_id: str
    thread_id: str


CALLS: list[str] = []


@tool
def publish_post(caption: str) -> str:
    """Publish a post (gated by approval)."""
    CALLS.append(caption)
    return f"published: {caption}"


class FakeDevice:
    name, mode = "fake", "live"

    async def list_devices(self):
        return [DeviceInfo(id="d1", name="iPhone", kind="iphone", status="ready", ready=True)]

    async def screenshot(self, device_id: str) -> bytes:
        return b"\xff\xd8jpeg"


def install_fake_graph(monkeypatch) -> None:
    """02-05 owns ugecy.graph; the runs manager only needs RunContext from it."""
    monkeypatch.setitem(sys.modules, "ugecy.graph", types.SimpleNamespace(RunContext=Ctx))


def call(name: str, args: dict, cid: str) -> dict:
    return {"name": name, "args": args, "id": cid}


def make_agent(script: list[AIMessage], subagent_script: list[AIMessage] | None = None):
    subagents = [{"name": "worker", "description": "w", "system_prompt": "x", "tools": [publish_post],
                  "model": ScriptedModel(script=subagent_script)}] if subagent_script else None
    return create_deep_agent(
        model=ScriptedModel(script=script), tools=[publish_post], subagents=subagents, context_schema=Ctx,
        interrupt_on={"publish_post": {"allowed_decisions": ["approve", "edit", "reject"]}},
        checkpointer=InMemorySaver(), store=InMemoryStore(), name="ugecy-orchestrator")


def make_deps(store: InMemoryStore | None = None) -> Deps:
    return Deps(settings=Settings(), modes=ProviderModes(media="live", device="live", publishing="live", research="live"), kv=None, app=MemAppStore(), edge=None,  # type: ignore[arg-type]
                research=None, media=None, device=FakeDevice(), publisher=None, analytics=None,  # type: ignore[arg-type]
                store=store or InMemoryStore())


def make_client(agent, deps: Deps | None = None) -> tuple[httpx.AsyncClient, Deps]:
    deps = deps or make_deps()
    app = create_app(agent=agent, deps=deps)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t"), deps


async def sse(client: httpx.AsyncClient, method: str, url: str, **kw) -> list[dict]:
    """Read an SSE response to the end; returns the decoded UiEvent dicts (also checks event: == type)."""
    events = []
    async with client.stream(method, url, **kw) as r:
        assert r.status_code == 200, await r.aread()
        assert r.headers["content-type"].startswith("text/event-stream")
        assert r.headers["x-accel-buffering"] == "no"
        name = None
        async for line in r.aiter_lines():
            if line.startswith("event:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data = json.loads(line.split(":", 1)[1])
                assert data["type"] == name
                events.append(data)
    return events

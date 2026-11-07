"""LangGraph astream(version="v2", subgraphs=True) parts -> UiEvents (packages/contracts/src/events.ts).

`StreamAdapter.feed(part)` is synchronous and holds only the de-dup state of one run. Anything async
(persisting approvals, cost estimates) is done by ugecy.runs on the events this returns.
"""
from __future__ import annotations

from typing import Any

import httpx
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

from ugecy import registry
from ugecy.contracts import ApprovalRequest, FileEntry, Todo, UiEvent
from ugecy.events import CUSTOM_TYPES

ORCHESTRATOR = "orchestrator"
_TOOL_PREVIEW, _SUMMARY = 2000, 600


def text_of(content: Any) -> str:
    """Message content (str or list of content blocks) -> plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b if isinstance(b, str) else str(b.get("text", ""))
                       for b in content if isinstance(b, str) or (isinstance(b, dict) and b.get("type") == "text"))
    return ""


def file_text(fd: dict[str, Any]) -> str:
    c = fd.get("content", "")
    return "\n".join(c) if isinstance(c, list) else str(c)


def agent_name(raw: str | None) -> str | None:
    if not raw:
        return None
    return ORCHESTRATOR if raw in ("ugecy-orchestrator", ORCHESTRATOR) else raw


def tool_owner(tool: str, fallback: str) -> str:
    return next((n for n, a in registry.AGENTS.items() if tool in a.tools), fallback)


def build_requests(value: dict[str, Any], fallback_agent: str = ORCHESTRATOR) -> list[ApprovalRequest]:
    """HITL interrupt value {action_requests, review_configs} -> ApprovalRequests."""
    configs = value.get("review_configs") or []
    by_name = {c.get("action_name"): c for c in configs}
    out = []
    for i, ar in enumerate(value.get("action_requests") or []):
        cfg = configs[i] if len(configs) == len(value["action_requests"]) else by_name.get(ar["name"], {})
        out.append(ApprovalRequest(
            tool=ar["name"], agent=tool_owner(ar["name"], fallback_agent), args=ar.get("args") or {},
            description=ar.get("description") or "", allowed_decisions=cfg.get("allowed_decisions")
            or ["approve", "edit", "reject"]))
    return out


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, TimeoutError | httpx.TimeoutException):
        return True
    low = f"{type(exc).__name__} {exc}".lower()
    return getattr(exc, "status_code", None) == 429 or "429" in low or "timeout" in low or "timed out" in low


class StreamAdapter:
    def __init__(self, thread_id: str, run_id: str, model: str | None = None) -> None:
        self.thread_id, self.run_id, self.model = thread_id, run_id, model
        self.interrupted = False
        self._seq = 0
        self._info: dict[tuple, tuple[str | None, str | None]] = {}  # ns -> (agent, parent_call_id)
        self._started: set[str] = set()
        self._done: set[str] = set()
        self._completed_msgs: set[str] = set()
        self._interrupts: set[str] = set()
        self._tasks: dict[str, str] = {}  # task call id -> subagent type
        self._todos: list[dict] = []
        self._files: dict[str, tuple] = {}

    # ---- lifecycle -----------------------------------------------------------------------
    def start(self) -> list[UiEvent]:
        return [self._ev("run.started", model=self.model)]

    def finish(self, cancelled: bool = False) -> list[UiEvent]:
        status = "cancelled" if cancelled else "interrupted" if self.interrupted else "done"
        return [self._ev("run.completed", status=status)]

    def fail(self, exc: BaseException) -> list[UiEvent]:
        return [self._ev("error", message=str(exc) or type(exc).__name__, retryable=is_retryable(exc)),
                self._ev("run.completed", status="error")]

    # ---- parts ---------------------------------------------------------------------------
    def feed(self, part: dict[str, Any]) -> list[UiEvent]:
        ns, data = tuple(part.get("ns") or ()), part.get("data")
        match part.get("type"):
            case "messages":
                return self._messages(ns, *data)
            case "updates":
                return self._updates(ns, data)
            case "values":
                return self._values(data) if not ns else []
            case "custom":
                return self._custom(ns, data)
        return []

    def _ev(self, type_: str, where: tuple[str, tuple, str | None] | None = None, **fields: Any) -> UiEvent:
        self._seq += 1
        agent, ns, parent = where or (ORCHESTRATOR, (), None)
        return UiEvent(type=type_, seq=self._seq, thread_id=self.thread_id, run_id=self.run_id,
                       agent=agent, ns=list(ns), parent_call_id=parent, **fields)  # type: ignore[arg-type]

    def _where(self, ns: tuple, md: dict | None = None, name: str | None = None) -> tuple[str, tuple, str | None]:
        md = md or {}
        known = self._info.get(ns, (None, None))
        agent = agent_name(md.get("lc_agent_name") or name) or known[0]
        parent = md.get("lc_subagent_tool_call_id") or known[1]
        if agent or parent:
            self._info[ns] = (agent, parent)
        if ns and not parent and ns[-1].startswith("tools:"):
            parent = ns[-1].removeprefix("tools:")  # shortcut: this is the task id, not the call id
        return (agent or (ORCHESTRATOR if not ns else ns[-1]), ns, parent)

    def _messages(self, ns: tuple, msg: Any, md: dict) -> list[UiEvent]:
        where = self._where(ns, md)
        if not isinstance(msg, AIMessageChunk):
            return []
        out = []
        if text := text_of(msg.content):
            out.append(self._ev("message.delta", where, message_id=msg.id or "", text=text))
        if reasoning := msg.additional_kwargs.get("reasoning_content"):
            out.append(self._ev("reasoning.delta", where, message_id=msg.id or "", text=str(reasoning)))
        return out

    def _updates(self, ns: tuple, data: dict) -> list[UiEvent]:
        out: list[UiEvent] = []
        for node, upd in data.items():
            if node == "__interrupt__":
                out += self._interrupt(ns, upd)
            elif isinstance(upd, dict) and isinstance(upd.get("messages"), list):
                for m in upd["messages"]:
                    if isinstance(m, AIMessage):
                        out += self._ai(ns, m)
                    elif isinstance(m, ToolMessage):
                        out += self._tool_done(ns, m)
        return out

    def _ai(self, ns: tuple, m: AIMessage) -> list[UiEvent]:
        where, out = self._where(ns, name=m.name), []
        if (text := text_of(m.content)) and m.id and m.id not in self._completed_msgs:
            self._completed_msgs.add(m.id)
            out.append(self._ev("message.completed", where, message_id=m.id, text=text))
        for tc in m.tool_calls:
            if tc["id"] in self._started:
                continue
            self._started.add(tc["id"])
            out.append(self._ev("tool.started", where, call_id=tc["id"], name=tc["name"], args=tc["args"]))
            if tc["name"] == "task":
                sub = str(tc["args"].get("subagent_type", ""))
                self._tasks[tc["id"]] = sub
                out.append(self._ev("subagent.started", where, call_id=tc["id"], subagent=sub,
                                    description=str(tc["args"].get("description", ""))))
        return out

    def _tool_done(self, ns: tuple, m: ToolMessage) -> list[UiEvent]:
        if m.tool_call_id in self._done:
            return []
        self._done.add(m.tool_call_id)
        where, text = self._where(ns), text_of(m.content)
        status = "error" if m.status == "error" else "ok"
        out = [self._ev("tool.completed", where, call_id=m.tool_call_id, name=m.name or "", status=status,
                        output_preview=text[:_TOOL_PREVIEW])]
        if m.name == "task":
            out.append(self._ev("subagent.completed", where, call_id=m.tool_call_id,
                                subagent=self._tasks.get(m.tool_call_id, ""), status=status,
                                summary=text[:_SUMMARY]))
        return out

    def _interrupt(self, ns: tuple, interrupts: Any) -> list[UiEvent]:
        out = []
        for it in interrupts:
            if it.id in self._interrupts or not isinstance(it.value, dict):
                continue
            self._interrupts.add(it.id)
            self.interrupted = True
            where = self._where(ns)
            out.append(self._ev("approval.requested", where, interrupt_id=it.id,
                                requests=build_requests(it.value, where[0])))
        return out

    def _values(self, state: dict) -> list[UiEvent]:
        out = []
        todos = [t for t in state.get("todos") or [] if isinstance(t, dict)]
        if todos != self._todos:
            self._todos = todos
            out.append(self._ev("todos.updated", todos=[Todo(**t) for t in todos]))
        files = {p: fd for p, fd in (state.get("files") or {}).items() if isinstance(fd, dict)}
        sig = {p: (len(file_text(fd)), fd.get("modified_at")) for p, fd in files.items()}
        if sig != self._files:
            self._files = sig
            out.append(self._ev("files.updated", files=[
                FileEntry(path=p, size=sig[p][0], modified_at=sig[p][1]) for p in sorted(files)]))
        return out

    def _custom(self, ns: tuple, data: Any) -> list[UiEvent]:
        if not isinstance(data, dict) or data.get("type") not in CUSTOM_TYPES:
            return []
        fields = {k: v for k, v in data.items() if k in UiEvent.model_fields and k not in
                  ("type", "seq", "ts", "thread_id", "run_id", "agent", "ns", "parent_call_id")}
        return [self._ev(data["type"], self._where(ns), **fields)]

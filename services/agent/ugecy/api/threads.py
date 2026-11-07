"""Threads: list/create/get/delete, plus the virtual files of a thread."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Request
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from ugecy.api.common import agent_of, deps_of, runs_of, thread_cfg
from ugecy.api.errors import ApiError
from ugecy.contracts import (
    ApprovalRecord,
    ChatMessage,
    CreateThreadRequest,
    FileContent,
    FileEntry,
    ThreadState,
    ThreadSummary,
    Todo,
    ToolCall,
)
from ugecy.stream.adapter import (
    ORCHESTRATOR,
    agent_name,
    build_requests,
    file_text,
    text_of,
)

router = APIRouter(prefix="/api/threads")
DEFAULT_TITLE = "New thread"


def to_chat_message(m: BaseMessage) -> ChatMessage:
    mid = m.id or f"msg_{uuid.uuid4().hex[:8]}"
    if isinstance(m, HumanMessage):
        return ChatMessage(id=mid, role="user", agent="operator", text=text_of(m.content))
    if isinstance(m, ToolMessage):
        return ChatMessage(id=mid, role="tool", agent=ORCHESTRATOR, text=text_of(m.content),
                           tool_call_id=m.tool_call_id, name=m.name)
    calls = [ToolCall(id=t["id"], name=t["name"], args=t["args"]) for t in getattr(m, "tool_calls", [])]
    reasoning = m.additional_kwargs.get("reasoning_content") if isinstance(m, AIMessage) else None
    return ChatMessage(id=mid, role="assistant", agent=agent_name(m.name) or ORCHESTRATOR, text=text_of(m.content),
                       reasoning=str(reasoning) if reasoning else None, tool_calls=calls)


def file_entries(files: dict[str, Any]) -> list[FileEntry]:
    return [FileEntry(path=p, size=len(file_text(fd)), modified_at=fd.get("modified_at"))
            for p, fd in sorted(files.items()) if isinstance(fd, dict)]


async def require_thread(request: Request, thread_id: str) -> ThreadSummary:
    thread = await deps_of(request).app.get_thread(thread_id)
    if thread is None:
        raise ApiError(404, "not_found", f"thread {thread_id} not found")
    return thread


@router.get("")
async def list_threads(request: Request) -> list[ThreadSummary]:
    threads = await deps_of(request).app.list_threads()
    return sorted(threads, key=lambda t: t.updated_at, reverse=True)


@router.post("")
async def create_thread(request: Request, body: CreateThreadRequest | None = None) -> ThreadSummary:
    thread = ThreadSummary(id=f"thr_{uuid.uuid4().hex[:12]}", title=(body and body.title) or DEFAULT_TITLE)
    await deps_of(request).app.upsert_thread(thread)
    return thread


@router.get("/{thread_id}")
async def get_thread(request: Request, thread_id: str) -> ThreadState:
    thread = await require_thread(request, thread_id)
    state = await agent_of(request).aget_state(thread_cfg(thread_id))
    values = state.values or {}
    pending = None
    if state.interrupts:
        it = state.interrupts[0]
        pending = await deps_of(request).app.get_approval(it.id) or ApprovalRecord(
            interrupt_id=it.id, thread_id=thread_id, requests=build_requests(it.value))
    return ThreadState(
        thread=thread, messages=[to_chat_message(m) for m in values.get("messages", [])],
        todos=[Todo(**t) for t in values.get("todos") or []], files=file_entries(values.get("files") or {}),
        sources=await deps_of(request).app.list_sources(thread_id), pending_approval=pending)


@router.delete("/{thread_id}")
async def delete_thread(request: Request, thread_id: str) -> dict[str, bool]:
    await runs_of(request).cancel(thread_id)
    runs_of(request).forget(thread_id)
    await deps_of(request).app.delete_thread(thread_id)
    # shortcut: the LangGraph checkpoint rows stay (no public delete on the saver Protocol), so old state is
    # orphaned until the checkpointer plan adds adelete_thread.
    return {"ok": True}


@router.get("/{thread_id}/files")
async def read_file(request: Request, thread_id: str, path: str) -> FileContent:
    await require_thread(request, thread_id)
    state = await agent_of(request).aget_state(thread_cfg(thread_id))
    fd = (state.values or {}).get("files", {}).get(path)
    if not isinstance(fd, dict):
        raise ApiError(404, "not_found", f"file {path} not found")
    return FileContent(path=path, content=file_text(fd))

"""Operator stop for one running subagent: the next model call or tool call inside it ends the subagent.

The orchestrator receives "Stopped by the operator." as the subagent's result and the rest of the run continues.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, hook_config
from langchain_core.messages import AIMessage, ToolMessage

STOPPED_TEXT = "Stopped by the operator."
_STOPPED: dict[str, set[str]] = defaultdict(set)  # thread_id -> subagent `task` call ids


def request_stop(thread_id: str, call_id: str) -> None:
    _STOPPED[thread_id].add(call_id)


def clear(thread_id: str) -> None:
    _STOPPED.pop(thread_id, None)


def is_stopped() -> bool:
    try:
        from langgraph.config import get_config

        cfg = get_config()
    except (RuntimeError, KeyError):
        return False
    call_id = (cfg.get("metadata") or {}).get("lc_subagent_tool_call_id")
    thread_id = (cfg.get("configurable") or {}).get("thread_id")
    return bool(call_id) and call_id in _STOPPED.get(thread_id, ())


class StopMiddleware(AgentMiddleware):
    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        if is_stopped():
            return {"messages": [AIMessage(content=STOPPED_TEXT)], "jump_to": "end"}
        return None

    async def awrap_tool_call(self, request: Any, handler: Any) -> Any:
        if is_stopped():
            return ToolMessage(content=STOPPED_TEXT, tool_call_id=request.tool_call["id"], status="error")
        return await handler(request)

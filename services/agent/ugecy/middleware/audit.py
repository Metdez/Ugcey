"""Writes one AuditEntry per tool call. Audit failures are logged and never break the tool call."""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage

from ugecy import registry
from ugecy.contracts import AuditEntry
from ugecy.deps import get_deps

log = logging.getLogger(__name__)
_MODE_FIELD = {"analytics": "publishing"}  # domains without their own ProviderModes field


def _context() -> tuple[str | None, str | None]:
    """(agent name, thread id) from the running langgraph config, best effort."""
    try:
        from langgraph.config import get_config

        cfg = get_config()
        return (cfg.get("metadata") or {}).get("lc_agent_name"), (cfg.get("configurable") or {}).get("thread_id")
    except Exception:  # noqa: BLE001 - outside a run
        return None, None


def _is_error(result: Any) -> bool:
    return isinstance(result, ToolMessage) and getattr(result, "status", None) == "error"


class AuditMiddleware(AgentMiddleware):
    name = "AuditMiddleware"

    async def _record(self, tool: str, args: Any, status: str) -> None:
        try:
            deps = get_deps()
            spec = registry.TOOLS.get(tool)
            domain = spec.domain if spec else "llm"
            mode = getattr(deps.modes, _MODE_FIELD.get(domain, domain), deps.modes.llm)
            agent, thread_id = _context()
            await deps.app.add_audit(AuditEntry(
                id=uuid.uuid4().hex, thread_id=thread_id, actor="agent", agent=agent, action="tool_call",
                tool=tool, status=status, mode=mode, detail=json.dumps(args, default=str)[:300]))  # type: ignore[arg-type]
        except Exception:
            log.warning("audit write failed for %s", tool, exc_info=True)

    async def awrap_tool_call(self, request, handler):
        call = request.tool_call
        try:
            result = await handler(request)
        except Exception:
            await self._record(call["name"], call.get("args"), "error")
            raise
        await self._record(call["name"], call.get("args"), "error" if _is_error(result) else "ok")
        return result

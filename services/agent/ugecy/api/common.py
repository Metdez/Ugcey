"""Shared request helpers: app-state accessors and the SSE response."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request
from sse_starlette import EventSourceResponse, ServerSentEvent

from ugecy.deps import Deps
from ugecy.runs import Run, RunManager

SSE_HEADERS = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}


def deps_of(request: Request) -> Deps:
    return request.app.state.deps


def agent_of(request: Request) -> Any:
    return request.app.state.agent


def runs_of(request: Request) -> RunManager:
    return request.app.state.runs


def thread_cfg(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def sse_response(runs: RunManager, run: Run, since: int = 0) -> EventSourceResponse:
    async def gen() -> AsyncIterator[ServerSentEvent]:
        async for ev in runs.subscribe(run, since):
            yield ServerSentEvent(data=json.dumps(ev.wire()), event=ev.type, id=str(ev.seq))

    return EventSourceResponse(gen(), ping=15, headers=SSE_HEADERS)

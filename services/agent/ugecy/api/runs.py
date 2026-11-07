"""Runs: start, resume (HITL), reconnect and cancel. Streams are SSE of UiEvent."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Header, Request
from langgraph.types import Command

from ugecy.api.common import agent_of, deps_of, runs_of, sse_response, thread_cfg
from ugecy.api.errors import ApiError
from ugecy.api.threads import DEFAULT_TITLE
from ugecy.contracts import (
    ApprovalRecord,
    AuditEntry,
    Decision,
    ResumeRequest,
    RunRequest,
    ThreadSummary,
    now_iso,
)
from ugecy.runs import RunConflict, tool_mode

router = APIRouter(prefix="/api/threads")


def _start(request: Request, thread_id: str, inp: Any):
    try:
        return runs_of(request).start(thread_id, inp)
    except RunConflict:
        raise ApiError(409, "run_active", "a run is already active on this thread") from None


@router.post("/{thread_id}/runs")
async def create_run(request: Request, thread_id: str, body: RunRequest):
    app = deps_of(request).app
    thread = await app.get_thread(thread_id)
    if thread is None:
        thread = ThreadSummary(id=thread_id, title=body.message[:60])
    elif thread.title == DEFAULT_TITLE:
        thread = thread.model_copy(update={"title": body.message[:60]})
    if runs_of(request).active(thread_id):
        raise ApiError(409, "run_active", "a run is already active on this thread")
    await app.upsert_thread(thread)
    run = _start(request, thread_id, {"messages": [{"role": "user", "content": body.message}]})
    return sse_response(runs_of(request), run)


def _wire_decision(d: Decision, tool: str, allowed: list[str]) -> dict[str, Any]:
    if d.type not in allowed:
        raise ApiError(422, "decision_not_allowed", f"{d.type} is not allowed for {tool}")
    if d.type == "edit":
        if d.args is None:
            raise ApiError(422, "validation_error", "edit decision needs args")
        return {"type": "edit", "edited_action": {"name": tool, "args": d.args}}
    if d.type == "reject":
        return {"type": "reject", "message": d.message or "Rejected by operator"}
    return {"type": "approve"}


@router.post("/{thread_id}/resume")
async def resume_run(request: Request, thread_id: str, body: ResumeRequest):
    deps = deps_of(request)
    state = await agent_of(request).aget_state(thread_cfg(thread_id))
    interrupts = list(state.interrupts or [])
    it = next((i for i in interrupts if i.id == body.interrupt_id), None)
    if it is None:
        raise ApiError(404, "no_pending_approval", f"no pending approval {body.interrupt_id}")
    actions = it.value["action_requests"]
    if len(body.decisions) != len(actions):
        raise ApiError(422, "validation_error", f"expected {len(actions)} decisions, got {len(body.decisions)}")
    allowed = {c["action_name"]: c["allowed_decisions"] for c in it.value.get("review_configs", [])}
    wire = [_wire_decision(d, a["name"], allowed.get(a["name"], ["approve", "edit", "reject"]))
            for d, a in zip(body.decisions, actions, strict=True)]
    payload = {"decisions": wire}
    run = _start(request, thread_id, Command(resume=payload if len(interrupts) == 1 else {it.id: payload}))

    kinds = {d.type for d in body.decisions}
    record = await deps.app.get_approval(it.id) or ApprovalRecord(
        interrupt_id=it.id, thread_id=thread_id, requests=[])
    status = "rejected" if "reject" in kinds else "edited" if "edit" in kinds else "approved"
    await deps.app.upsert_approval(record.model_copy(update={"status": status, "decided_at": now_iso()}))
    for d, a in zip(body.decisions, actions, strict=True):
        await deps.app.add_audit(AuditEntry(
            id=f"aud_{uuid.uuid4().hex[:12]}", thread_id=thread_id, actor="operator", action="approval",
            tool=a["name"], status="rejected" if d.type == "reject" else "ok", mode=tool_mode(deps, a["name"]),
            detail=d.type if d.type != "reject" else f"reject: {d.message or ''}"))
    return sse_response(runs_of(request), run)


@router.get("/{thread_id}/stream")
async def reconnect(request: Request, thread_id: str, since: int = 0,
                    last_event_id: str | None = Header(default=None)):
    run = runs_of(request).latest(thread_id)
    if run is None:
        raise ApiError(404, "no_run", "no run to stream on this thread")
    if last_event_id and last_event_id.isdigit():
        since = max(since, int(last_event_id))
    return sse_response(runs_of(request), run, since)


@router.post("/{thread_id}/subagents/{call_id}/stop")
async def stop_subagent(request: Request, thread_id: str, call_id: str) -> dict[str, bool]:
    """Stop one running subagent (by its `task` call id); the rest of the run continues."""
    from ugecy.middleware.stop import request_stop

    request_stop(thread_id, call_id)
    return {"ok": True}


@router.post("/{thread_id}/cancel")
async def cancel_run(request: Request, thread_id: str) -> dict[str, bool]:
    return {"ok": await runs_of(request).cancel(thread_id)}

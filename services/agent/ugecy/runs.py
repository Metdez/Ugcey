"""RunManager: one background asyncio task per active run, independent of any HTTP client.

Events go through StreamAdapter into a per-run buffer; SSE subscribers read it from `since`.
The last run's buffer per thread is kept for reconnect.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from ugecy.contracts import ApprovalRecord, AuditEntry, UiEvent, now_iso
from ugecy.deps import Deps
from ugecy.stream.adapter import StreamAdapter

log = logging.getLogger("ugecy.runs")
_THREAD_STATUS = {"done": "idle", "cancelled": "idle", "interrupted": "awaiting_approval", "error": "error"}


class RunConflict(Exception):
    """A run is already active on the thread."""


class Run:
    def __init__(self, thread_id: str) -> None:
        self.id = f"run_{uuid.uuid4().hex[:12]}"
        self.thread_id = thread_id
        self.events: list[UiEvent] = []  # seq == index + 1
        self.cond = asyncio.Condition()
        self.done = False
        self.task: asyncio.Task | None = None


def _default_context(workspace_id: str, thread_id: str) -> Any:
    # 02-05 owns ugecy.graph; imported late so this module loads without it
    from ugecy.graph import RunContext

    fields = {"workspace_id": workspace_id, "thread_id": thread_id}  # 02-05 may omit thread_id
    return RunContext(**{k: v for k, v in fields.items() if k in RunContext.__dataclass_fields__})


class RunManager:
    def __init__(self, get_agent: Callable[[], Any], get_deps: Callable[[], Deps]) -> None:
        self._agent, self._deps = get_agent, get_deps
        self._runs: dict[str, Run] = {}  # latest run per thread

    def latest(self, thread_id: str) -> Run | None:
        return self._runs.get(thread_id)

    def active(self, thread_id: str) -> Run | None:
        run = self._runs.get(thread_id)
        return run if run and not run.done else None

    def start(self, thread_id: str, inp: Any) -> Run:
        if self.active(thread_id):
            raise RunConflict(thread_id)
        run = Run(thread_id)
        self._runs[thread_id] = run
        run.task = asyncio.create_task(self._drive(run, inp), name=f"run-{run.id}")
        return run

    async def cancel(self, thread_id: str) -> bool:
        run = self.active(thread_id)
        if not run or not run.task:
            return False
        run.task.cancel()
        await asyncio.gather(run.task, return_exceptions=True)
        return True

    async def shutdown(self) -> None:
        await asyncio.gather(*(self.cancel(t) for t in list(self._runs)))

    def forget(self, thread_id: str) -> None:
        self._runs.pop(thread_id, None)

    async def subscribe(self, run: Run, since: int = 0) -> AsyncIterator[UiEvent]:
        i = max(since, 0)
        while True:
            async with run.cond:
                await run.cond.wait_for(lambda n=i: len(run.events) > n or run.done)
                batch = run.events[i:]
            if not batch:
                return
            i += len(batch)
            for ev in batch:
                yield ev

    # ---- internals -----------------------------------------------------------------------
    async def _drive(self, run: Run, inp: Any) -> None:
        deps, tid = self._deps(), run.thread_id
        s = deps.settings
        adapter = StreamAdapter(tid, run.id, model=s.model_orchestrator)
        await self._set_status(tid, "running")
        await self._publish(run, adapter.start())
        try:
            cfg = {"configurable": {"thread_id": tid}, "recursion_limit": 400}
            async for part in self._agent().astream(
                    inp, config=cfg, context=_default_context(s.workspace_id, tid), version="v2", subgraphs=True,
                    stream_mode=["messages", "updates", "custom", "values"]):
                await self._publish(run, adapter.feed(part))
            final = adapter.finish()
        except asyncio.CancelledError:
            final = adapter.finish(cancelled=True)
        except Exception as exc:
            log.exception("run %s failed", run.id)
            final = adapter.fail(exc)
        status = final[-1].status or "error"
        try:
            await self._publish(run, final)
            await self._set_status(tid, _THREAD_STATUS[status])
        finally:
            async with run.cond:
                run.done = True
                run.cond.notify_all()

    async def _publish(self, run: Run, events: list[UiEvent]) -> None:
        deps = self._deps()
        for ev in events:
            if ev.type == "approval.requested":
                await self._record_approval(run, ev, deps)
            elif ev.type == "source.added" and ev.source:
                try:
                    await deps.app.add_source(run.thread_id, ev.source)
                except Exception:
                    log.exception("add_source failed")
        async with run.cond:
            run.events.extend(events)
            run.cond.notify_all()

    async def _record_approval(self, run: Run, ev: UiEvent, deps: Deps) -> None:
        for req in ev.requests or []:
            if req.tool == "generate_media":
                try:
                    from ugecy.tools.media import estimate_for_approval  # 02-08

                    req.estimated_cost_usd = await estimate_for_approval(req.args)
                except Exception:
                    log.exception("cost estimate failed")
            await deps.app.add_audit(AuditEntry(
                id=f"aud_{uuid.uuid4().hex[:12]}", thread_id=run.thread_id, actor="agent", agent=req.agent,
                action="approval", tool=req.tool, status="pending", mode=tool_mode(deps, req.tool),
                detail=req.description[:500]))
        await deps.app.upsert_approval(ApprovalRecord(
            interrupt_id=ev.interrupt_id or "", thread_id=run.thread_id, requests=ev.requests or []))

    async def _set_status(self, thread_id: str, status: str) -> None:
        app = self._deps().app
        if thread := await app.get_thread(thread_id):
            await app.upsert_thread(thread.model_copy(update={"status": status, "updated_at": now_iso()}))


def tool_mode(deps: Deps, tool: str) -> str:
    """Provider mode ("live"/"mock") of the domain a tool belongs to, for audit entries."""
    from ugecy import registry

    spec = registry.TOOLS.get(tool)
    return getattr(deps.modes, spec.domain, "live") if spec else "live"

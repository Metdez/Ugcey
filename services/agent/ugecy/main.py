"""App factory. `app` (uvicorn target) runs the full startup in its lifespan; tests call
create_app(agent=..., deps=...) to inject a prepared agent and container instead."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from ugecy.api import install_api
from ugecy.contracts import ConnectedAccount
from ugecy.deps import Deps, build_deps, set_deps
from ugecy.interfaces import AppStore
from ugecy.modules import load_modules
from ugecy.runs import RunManager
from ugecy.settings import get_settings

DEMO_HANDLE = "@demo_brand"


async def ensure_default_accounts(app_store: AppStore) -> None:
    if await app_store.list_accounts():
        return
    for platform in ("tiktok", "instagram", "youtube"):
        await app_store.upsert_account(ConnectedAccount(
            id=f"acct_{platform}_demo", platform=platform, handle=DEMO_HANDLE, mode="mock"))  # type: ignore[arg-type]


async def _startup(app: FastAPI) -> Deps:
    # 02-05 / 02-06 modules are imported here so ugecy.main stays importable without them.
    from ugecy.graph import build_agent, seed_store
    from ugecy.persistence import build_checkpointer, build_store

    settings = get_settings()
    deps = build_deps(settings)
    await deps.app.init()
    deps.checkpointer = build_checkpointer(deps.kv)
    deps.store = await build_store(deps.kv)
    load_modules()
    await seed_store(deps.store, settings.workspace_id)
    set_deps(deps)
    app.state.deps = deps
    app.state.agent = build_agent(deps)
    await ensure_default_accounts(deps.app)
    try:  # re-poll media jobs orphaned by a restart; never block startup
        from ugecy.tools.media import resume_media_jobs
        await resume_media_jobs()
    except Exception:
        logging.getLogger(__name__).exception("resume_media_jobs failed")
    return deps


def create_app(agent: Any = None, deps: Deps | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if deps is None:
            await _startup(app)
        yield
        await app.state.runs.shutdown()  # SIGTERM: stop runs; checkpoints are already saved per step

    app = FastAPI(title="ugecy-agent", lifespan=lifespan)
    app.state.runs = RunManager(lambda: app.state.agent, lambda: app.state.deps)
    if deps is not None:  # injected (tests)
        set_deps(deps)
        app.state.deps, app.state.agent = deps, agent

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True, "service": "ugecy-agent"}

    install_api(app)
    return app


app = create_app()

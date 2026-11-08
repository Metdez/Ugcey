"""Config, health, device and the plain AppStore reads (assets, approvals, audit, accounts, posts)."""
from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Request, Response

from ugecy import registry
from ugecy.api.common import deps_of
from ugecy.api.errors import ApiError
from ugecy.contracts import (
    AgentInfo,
    AppConfig,
    ApprovalRecord,
    Asset,
    AuditEntry,
    ConnectedAccount,
    DeviceStatus,
    ModelRoute,
    Post,
)
from ugecy.integrations.unavailable import DEVICE_OFF
from ugecy.settings import get_settings

router = APIRouter()

STARTER_PROMPTS = [
    "Find the top 20 TikTok UGC hooks for clean skincare this month and explain why they work.",
    "Break these 5 videos into hook, script structure and CTA patterns.",
    "Write 5 original 30-second UGC scripts for our serum using the top patterns.",
    "Generate 3 vertical UGC-style videos for script #2 with Higgsfield.",
    "Schedule the approved videos to @glowco on TikTok and Instagram this week.",
    "How did last week's posts perform? What should we make next?",
]
_ROLES = ("orchestrator", "research", "creative", "critic", "fast", "vision")


@router.get("/api/healthz")
async def api_healthz() -> dict:
    return {"ok": True, "service": "ugecy-agent", "version": get_settings().version}


@router.get("/api/config")
async def config(request: Request) -> AppConfig:
    deps = deps_of(request)
    s = deps.settings
    disabled = s.disabled("agents")
    models = [ModelRoute(role=r, model=s.model_for(r), fallback=s.model_fallback) for r in _ROLES]
    models.append(ModelRoute(role="embeddings", model=s.model_embeddings))
    agents = [AgentInfo(name="orchestrator", description="Plans the campaign and delegates to specialist agents.",
                        model=s.model_orchestrator, tools=[])]
    agents += [AgentInfo(name=a.name, description=a.description, model=s.model_for(a.model_role), tools=a.tools,
                         enabled=a.enabled and a.name not in disabled) for a in registry.AGENTS.values()]
    return AppConfig(version=s.version, modes=await _live_modes(deps), models=models, agents=agents,
                     starter_prompts=STARTER_PROMPTS)


async def _live_modes(deps):
    """Device and publishing follow the iPhone at request time: publishing runs through the connected phone."""
    try:
        ready = any(d.ready for d in await asyncio.wait_for(deps.device.list_devices(), 8))
    except Exception:  # noqa: BLE001 unreachable device = off
        ready = False
    phone = "live" if ready else "off"
    try:
        from ugecy.integrations.storage.dropbox import get_dropbox
        storage = "live" if await asyncio.wait_for(get_dropbox().connected(), 8) else "off"
    except Exception:  # noqa: BLE001
        storage = "off"
    return deps.modes.model_copy(update={"device": phone, "publishing": phone, "storage": storage})


_LINKS: dict[str, tuple[str, float]] = {}  # dropbox path -> (temporary link, expiry); links last 4 h
_LINK_AFTER = timedelta(days=6, hours=12)  # Higgsfield deletes outputs at 7 days


async def _durable(a: Asset) -> Asset:
    """After Higgsfield deletes an output, serve it from the operator's Dropbox (private 4 h link)."""
    if a.dropbox_status != "saved" or not a.dropbox_path:
        return a
    try:
        if datetime.now(UTC) - datetime.fromisoformat(a.created_at) < _LINK_AFTER:
            return a
        from ugecy.integrations.storage.dropbox import get_dropbox
        link, exp = _LINKS.get(a.dropbox_path, ("", 0.0))
        if exp < time.time():
            link, exp = await get_dropbox().temp_link(a.dropbox_path), time.time() + 3.5 * 3600
            _LINKS[a.dropbox_path] = (link, exp)
    except Exception:  # noqa: BLE001 - keep the stored url
        return a
    return a.model_copy(update={"url": link, "thumbnail_url": link if a.kind == "image" else a.thumbnail_url})


@router.get("/api/assets")
async def assets(request: Request, thread_id: str | None = None) -> list[Asset]:
    return list(await asyncio.gather(*[_durable(a) for a in await deps_of(request).app.list_assets(thread_id)]))


@router.post("/api/storage/backfill")
async def storage_backfill(retry_failed: bool = False) -> dict:
    from ugecy.storage.backup import reconcile

    return {"queued": await reconcile(retry_failed)}


@router.get("/api/approvals")
async def approvals(request: Request, status: str | None = None) -> list[ApprovalRecord]:
    return await deps_of(request).app.list_approvals(status)


@router.get("/api/audit")
async def audit(request: Request, thread_id: str | None = None, limit: int = 100) -> list[AuditEntry]:
    return await deps_of(request).app.list_audit(thread_id, limit)


@router.get("/api/accounts")
async def accounts(request: Request) -> list[ConnectedAccount]:
    return await deps_of(request).app.list_accounts()


@router.get("/api/posts")
async def posts(request: Request, thread_id: str | None = None) -> list[Post]:
    return await deps_of(request).app.list_posts(thread_id)


@router.get("/api/device")
async def device(request: Request) -> DeviceStatus:
    from ugecy.tools.device import device_status_snapshot  # 02-08

    return await device_status_snapshot()


@router.get("/api/device/screenshot")
async def device_screenshot(request: Request) -> Response:
    devices = await deps_of(request).device.list_devices()
    if not devices:
        raise ApiError(503, "not_connected", DEVICE_OFF)
    try:
        jpeg = await deps_of(request).device.screenshot(devices[0].id)  # already cropped to the viewport
    except httpx.HTTPError as e:
        raise ApiError(503, "screenshot_unavailable", f"device capture failed ({type(e).__name__}); retry") from e
    return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

"""Copy every finished Higgsfield output into the operator's Dropbox with save_url (Dropbox pulls the URL itself).

- backup_asset: one asset. Idempotent: a file already at the target path counts as saved.
- reconcile: every completed asset not yet saved (startup, right after Connect, the dropbox_backfill tool).
- schedule_backup: fire-and-forget hook after a media job completes.
Not connected => nothing is written; the asset stays unsaved and the next reconcile picks it up.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

from ugecy.contracts import Asset, AuditEntry
from ugecy.integrations.storage.dropbox import DropboxError, get_dropbox
from ugecy.integrations.unavailable import NotConnected

log = logging.getLogger(__name__)
ROOT = "/Ugecy"
FOLDERS = {"video": "Videos", "image": "Images", "audio": "Audio"}
EXT = {"video": ".mp4", "image": ".png", "audio": ".mp3"}
KNOWN_EXT = {".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp3", ".wav", ".m4a"}
JOB_POLL_S = 3.0
TRANSFER_WINDOW_S = 16 * 60  # Dropbox fails a save_url transfer after 15 minutes; poll a little past that
PARALLEL = 3  # Dropbox rate-limits bursts of writes per user
PHONE_STEPS = ("On the iPhone: open the Dropbox app, tap Search and type the file name (or Files > Ugecy > "
               "Videos/Images), tap ••• next to the file > Export > Save video (or Save image). It is then in "
               "Photos, ready to pick in TikTok/Instagram/YouTube.")
_TASKS: set[asyncio.Task] = set()
_ACTIVE: set[str] = set()
_SEM: asyncio.Semaphore | None = None


def _slug(text: str, n: int = 40) -> str:
    words = re.sub(r"[^A-Za-z0-9 ]+", " ", text).split()[:7]
    return " ".join(words)[:n].strip().lower() or "media"


def dropbox_path(asset: Asset) -> str:
    ext = PurePosixPath(urlparse(asset.url or "").path).suffix.lower()
    if ext not in KNOWN_EXT:
        ext = EXT[asset.kind]
    day = (asset.created_at or "")[:10] or datetime.now(UTC).strftime("%Y-%m-%d")
    return f"{ROOT}/{FOLDERS[asset.kind]}/{day} {_slug(asset.prompt)} {asset.id[:8]}{ext}"


def _sem() -> asyncio.Semaphore:
    global _SEM
    if _SEM is None:
        _SEM = asyncio.Semaphore(PARALLEL)
    return _SEM


async def _audit(asset: Asset, status: str, detail: str) -> None:
    from uuid import uuid4

    from ugecy.deps import get_deps

    try:
        await get_deps().app.add_audit(AuditEntry(id=uuid4().hex, thread_id=asset.thread_id, actor="agent",
                                                  action="dropbox_backup", tool="save_to_dropbox", status=status,  # type: ignore[arg-type]
                                                  mode="live", detail=detail[:500]))
    except Exception:
        log.warning("audit write failed for dropbox backup", exc_info=True)


async def _mark(asset: Asset, path: str | None, status: str) -> Asset:
    from ugecy.deps import get_deps
    from ugecy.events import emit

    await get_deps().app.set_asset_dropbox(asset.id, path, status)
    updated = asset.model_copy(update={"dropbox_path": path, "dropbox_status": status})
    emit("asset.updated", asset=updated.model_dump(mode="json"))  # no-op outside a run; the Assets tab polls
    return updated


async def _wait(job_id: str) -> dict[str, Any]:
    dbx, waited = get_dropbox(), 0.0
    while waited < TRANSFER_WINDOW_S:
        r = await dbx.check_job(job_id)
        if r.get(".tag") != "in_progress":
            return r
        await asyncio.sleep(JOB_POLL_S)
        waited += JOB_POLL_S
    return {".tag": "failed", "failed": {".tag": "transfer timed out (Dropbox limit is 15 minutes)"}}


async def backup_asset(asset_id: str) -> dict[str, Any]:
    """Save one asset to Dropbox now. Returns {asset_id, status, dropbox_path} or {asset_id, error}."""
    from ugecy.deps import get_deps

    asset = await get_deps().app.get_asset(asset_id)
    if asset is None:
        return {"asset_id": asset_id, "error": "unknown asset"}
    if asset.dropbox_status == "saved":
        return {"asset_id": asset_id, "status": "saved", "dropbox_path": asset.dropbox_path}
    if asset.status != "completed" or not (asset.url or "").startswith("http"):
        return {"asset_id": asset_id, "error": f"asset is {asset.status}; only completed media with a URL can be saved"}
    if asset_id in _ACTIVE:
        return {"asset_id": asset_id, "status": "pending", "dropbox_path": dropbox_path(asset)}
    _ACTIVE.add(asset_id)
    path = dropbox_path(asset)
    try:
        async with _sem():
            dbx = get_dropbox()
            if not await dbx.connected():
                raise NotConnected("Dropbox not connected")
            if await dbx.get_metadata(path):
                await _mark(asset, path, "saved")
                return {"asset_id": asset_id, "status": "saved", "dropbox_path": path}
            await _mark(asset, path, "pending")
            r = await dbx.save_url(path, asset.url or "")
            if r.get(".tag") == "async_job_id":
                r = await _wait(r["async_job_id"])
            if r.get(".tag") == "complete":
                await _mark(asset, (r.get("path_display") or path), "saved")
                await _audit(asset, "ok", f"saved {asset.kind} to Dropbox {path}")
                return {"asset_id": asset_id, "status": "saved", "dropbox_path": r.get("path_display") or path}
            reason = str((r.get("failed") or {}).get(".tag") or r)
            raise DropboxError(409, reason)
    except NotConnected as e:
        if asset.dropbox_status == "pending":
            await get_deps().app.set_asset_dropbox(asset.id, None, None)
        return {"asset_id": asset_id, "error": str(e)}
    except DropboxError as e:
        if "conflict" in e.summary and await get_dropbox().get_metadata(path):
            await _mark(asset, path, "saved")
            return {"asset_id": asset_id, "status": "saved", "dropbox_path": path}
        await _mark(asset, path, "failed")
        await _audit(asset, "error", f"Dropbox save failed: {e.summary}")
        return {"asset_id": asset_id, "error": f"Dropbox save failed: {e.summary}"}
    except Exception as e:
        log.warning("dropbox backup failed for %s", asset_id, exc_info=True)
        await get_deps().app.set_asset_dropbox(asset.id, None, None)
        return {"asset_id": asset_id, "error": f"{type(e).__name__}: will retry on the next backfill"}
    finally:
        _ACTIVE.discard(asset_id)


def _spawn(coro: Any) -> None:
    t = asyncio.get_running_loop().create_task(coro)
    _TASKS.add(t)
    t.add_done_callback(_TASKS.discard)


def schedule_backup(asset_id: str) -> None:
    _spawn(backup_asset(asset_id))


async def pending_assets(retry_failed: bool = False) -> list[Asset]:
    from ugecy.deps import get_deps

    todo = {None, "pending", *(("failed",) if retry_failed else ())}
    return [a for a in await get_deps().app.list_assets()
            if a.status == "completed" and (a.url or "").startswith("http") and a.dropbox_status in todo]


async def reconcile(retry_failed: bool = False) -> int:
    """Queue a backup for every completed asset not yet in Dropbox. Returns how many were queued."""
    if not await get_dropbox().connected():
        return 0
    todo = await pending_assets(retry_failed)
    for a in todo:
        schedule_backup(a.id)
    return len(todo)


async def drain() -> None:
    while _TASKS:
        await asyncio.gather(*list(_TASKS), return_exceptions=True)

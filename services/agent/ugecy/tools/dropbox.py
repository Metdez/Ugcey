"""Dropbox media library tools. Every Higgsfield output is copied to the operator's Dropbox automatically
(ugecy.storage.backup); these let agents see, find and (re)save those files. No approval: not posting or payment."""
from __future__ import annotations

import json

from langchain_core.tools import tool

from ugecy.deps import get_deps
from ugecy.integrations.storage.dropbox import DropboxError, get_dropbox
from ugecy.integrations.unavailable import STORAGE_OFF, NotConnected
from ugecy.registry import register_tool
from ugecy.storage import backup


async def _off() -> str | None:
    return None if await get_dropbox().connected() else json.dumps({"error": STORAGE_OFF})


@tool
async def dropbox_status() -> str:
    """Is the operator's Dropbox connected? Returns account, missing permissions and how many media files are saved."""
    st = await get_dropbox().status(fresh=True)
    assets = [a for a in await get_deps().app.list_assets() if a.status == "completed"]
    saved = sum(a.dropbox_status == "saved" for a in assets)
    return json.dumps({**st, "root": backup.ROOT, "saved": saved, "not_saved": len(assets) - saved,
                       "note": None if st.get("connected") else STORAGE_OFF})


@tool
async def list_dropbox_media(kind: str = "", limit: int = 20) -> str:
    """Newest media saved to Dropbox (kind: video|image|audio or empty for all), with each file's Dropbox path and the
    steps to find it in the Dropbox app on the iPhone. Use this to know which file to post from the phone. After saving a
    video from the Dropbox app, never open the Photos app to verify it: it is the newest item in the posting app's picker."""
    if err := await _off():
        return err
    items = [a for a in await get_deps().app.list_assets()
             if a.dropbox_status == "saved" and (not kind or a.kind == kind)][: max(1, limit)]
    return json.dumps({"files": [{"asset_id": a.id, "kind": a.kind, "file_name": (a.dropbox_path or "").rsplit("/", 1)[-1],
                                  "dropbox_path": a.dropbox_path, "created_at": a.created_at, "model": a.model,
                                  "prompt": a.prompt[:120], "thread_id": a.thread_id} for a in items],
                       "phone_steps": backup.PHONE_STEPS})


@tool
async def browse_dropbox(path: str = "/Ugecy", limit: int = 50) -> str:
    """List files under a Dropbox folder (recursive), newest first: name, path, size and modified time."""
    try:
        entries = await get_dropbox().list_folder(path, limit=max(1, limit) * 4)
    except NotConnected:
        return json.dumps({"error": STORAGE_OFF})
    except DropboxError as e:
        return json.dumps({"error": e.summary})
    files = sorted((e for e in entries if e.get(".tag") == "file"), key=lambda e: e.get("server_modified", ""), reverse=True)
    return json.dumps({"path": path, "files": [{"name": e["name"], "path": e.get("path_display"), "size": e.get("size"),
                                                "modified": e.get("server_modified")} for e in files[: max(1, limit)]]})


@tool
async def save_to_dropbox(asset_id: str) -> str:
    """Save one completed media asset to Dropbox now (normally automatic). Returns its Dropbox path."""
    if err := await _off():
        return err
    return json.dumps({**await backup.backup_asset(asset_id), "phone_steps": backup.PHONE_STEPS})


@tool
async def dropbox_backfill(retry_failed: bool = False) -> str:
    """Copy every completed media asset that is not in Dropbox yet (runs in the background)."""
    if err := await _off():
        return err
    return json.dumps({"queued": await backup.reconcile(retry_failed), "root": backup.ROOT})


for _t in (dropbox_status, list_dropbox_media, browse_dropbox, save_to_dropbox, dropbox_backfill):
    register_tool(_t, domain="storage")

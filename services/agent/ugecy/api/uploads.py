"""Product photo uploads: the operator attaches a photo to a thread; it becomes an image Asset the agents can chain
into Marketing Studio stills (reference_asset_ids) and end frames (end_image_asset_id)."""
from __future__ import annotations

import base64
import binascii
import uuid

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel

from ugecy.api.common import deps_of
from ugecy.api.errors import ApiError
from ugecy.api.threads import require_thread
from ugecy.contracts import Asset, AuditEntry
from ugecy.integrations.unavailable import NotConnected

router = APIRouter(prefix="/api/threads")

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 10 * 1024 * 1024


class UploadRequest(BaseModel):
    filename: str
    content_type: str
    data_base64: str


@router.post("/{thread_id}/uploads")
async def upload_product_photo(request: Request, thread_id: str, body: UploadRequest) -> Asset:
    await require_thread(request, thread_id)
    ctype = body.content_type.lower().strip()
    if ctype == "image/jpg":
        ctype = "image/jpeg"
    if ctype not in ALLOWED_TYPES:
        raise ApiError(415, "unsupported_type", "Product photos must be JPEG, PNG or WebP.")
    if len(body.data_base64) > MAX_BYTES * 4 // 3 + 4:
        raise ApiError(413, "too_large", "Product photos must be 10 MB or smaller.")
    try:
        data = base64.b64decode(body.data_base64, validate=True)
    except (binascii.Error, ValueError):
        raise ApiError(422, "validation_error", "data_base64 is not valid base64") from None
    if not data:
        raise ApiError(422, "validation_error", "the file is empty")
    if len(data) > MAX_BYTES:
        raise ApiError(413, "too_large", "Product photos must be 10 MB or smaller.")

    deps = deps_of(request)
    try:
        url = await deps.media.upload(data, ctype)
    except NotConnected as e:
        raise ApiError(503, "media_off", str(e)) from None
    except (RuntimeError, httpx.HTTPError, KeyError) as e:  # relay or storage refused, network error, bad response
        raise ApiError(502, "upload_failed", str(e)) from None

    name = body.filename.strip()[:120] or "product photo"
    asset = Asset(id=f"asset_{uuid.uuid4().hex[:12]}", thread_id=thread_id, kind="image", status="completed",
                  provider="upload", model="upload", prompt=name, url=url, mode=deps.media.mode)
    await deps.app.upsert_asset(asset)
    await deps.app.add_audit(AuditEntry(id=f"aud_{uuid.uuid4().hex[:12]}", thread_id=thread_id, actor="operator",
                                        action="upload", tool="upload_product_photo", status="ok", mode=deps.media.mode,
                                        detail=f"{name} ({ctype}, {len(data)} bytes) -> {asset.id}"))
    return asset

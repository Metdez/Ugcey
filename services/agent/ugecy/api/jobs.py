"""Internal jobs called by Cloudflare Workflows. Deliberately not under /api: the Worker never exposes them."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header
from pydantic import BaseModel

from ugecy.api.errors import ApiError

router = APIRouter(prefix="/jobs")
_RESULTS: dict[str, dict] = {}  # shortcut: per-process replay cache; run_publish_job itself must be idempotent per post


class PublishJob(BaseModel):
    post_id: str


@router.post("/publish")
async def publish(body: PublishJob, idempotency_key: Annotated[str | None, Header()] = None) -> dict:
    if not idempotency_key:
        raise ApiError(400, "idempotency_key_required", "Idempotency-Key header is required")
    if idempotency_key not in _RESULTS:
        from ugecy.tools.publishing import run_publish_job  # 02-08

        _RESULTS[idempotency_key] = await run_publish_job(body.post_id)
    return _RESULTS[idempotency_key]

"""Higgsfield REST adapter (INTEGRATIONS.md B2-B5). Thin httpx client, not the SDK: the SDK
retries billable POSTs without an Idempotency-Key. Here a POST is only retried (on 429) with the same key.

Edge mode talks to http://higgsfield.internal (the Worker injects auth). Local mode talks to
api.higgsfield.ai with `Authorization: Key <id:secret>`. The key is never logged or put in errors.
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from ugecy.integrations.media.catalog import catalog_models
from ugecy.interfaces import MediaJob
from ugecy.settings import Settings

_MAX_RETRY_WAIT_S = 30.0
_ATTEMPTS = 3
_STATUSES = {"queued", "in_progress", "completed", "failed", "nsfw", "canceled"}


class HiggsfieldError(RuntimeError):
    def __init__(self, status: int, detail: str, correlation_id: str | None = None):
        super().__init__(f"higgsfield HTTP {status}: {detail}" + (f" (correlation {correlation_id})" if correlation_id else ""))
        self.status = status


def map_outputs(body: dict[str, Any]) -> list[dict[str, str]]:
    outs = [{"url": i["url"], "kind": "image"} for i in body.get("images") or [] if i.get("url")]
    for key, kind in (("video", "video"), ("audio", "audio")):
        if isinstance(body.get(key), dict) and body[key].get("url"):
            outs.append({"url": body[key]["url"], "kind": kind})
    return outs


def _detail(resp: httpx.Response) -> str:
    try:
        d = resp.json().get("detail", resp.text)
    except Exception:
        return resp.text[:200]
    return (d.get("message") or str(d)) if isinstance(d, dict) else str(d)[:200]


class HiggsfieldProvider:
    name = "higgsfield"
    mode = "live"

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        edge = settings.internal_mode == "edge"
        headers: dict[str, str] = {}
        if not edge:
            key = settings.higgsfield_key
            if not key:
                raise RuntimeError("Higgsfield key missing (set HF_KEY or HF_API_KEY_SECRET) or use media_provider=mock")
            headers["Authorization"] = f"Key {key}"
        self._client = httpx.AsyncClient(
            base_url="http://higgsfield.internal" if edge else "https://api.higgsfield.ai",
            headers=headers, timeout=30.0, transport=transport,
        )

    def models(self, kind: str | None = None) -> list[dict[str, Any]]:
        return catalog_models(kind)

    async def _request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        for attempt in range(_ATTEMPTS):
            resp = await self._client.request(method, path, **kw)
            if resp.status_code == 429 and attempt < _ATTEMPTS - 1:
                try:  # retrying a POST here is safe: callers always send the same Idempotency-Key
                    wait = float(resp.headers.get("Retry-After", "2"))
                except ValueError:
                    wait = 2.0
                await asyncio.sleep(min(max(wait, 0.0), _MAX_RETRY_WAIT_S))
                continue
            if resp.status_code >= 400:
                raise HiggsfieldError(resp.status_code, _detail(resp), resp.headers.get("X-Correlation-ID"))
            return resp
        raise AssertionError("unreachable")

    async def estimate(self, model: str, args: dict[str, Any]) -> float | None:
        try:
            return float((await self._request("POST", f"/estimate/{model}", json=args)).json()["usd"])
        except (HiggsfieldError, httpx.HTTPError, KeyError, ValueError, TypeError):
            return None

    async def submit(self, model: str, args: dict[str, Any], *, idempotency_key: str) -> MediaJob:
        resp = await self._request("POST", f"/{model}", json=args, headers={"Idempotency-Key": idempotency_key})
        return self._job(resp.json())

    async def get(self, job_id: str) -> MediaJob:
        return self._job((await self._request("GET", f"/requests/{job_id}/status")).json(), job_id)

    @staticmethod
    def _job(body: dict[str, Any], job_id: str | None = None) -> MediaJob:
        status = body.get("status", "queued")
        payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
        return MediaJob(
            job_id=body.get("request_id") or job_id or "",
            status=status if status in _STATUSES else "failed",
            outputs=map_outputs(payload) if status == "completed" else [],
            error=str(body["error"])[:300] if body.get("error") else None,
        )

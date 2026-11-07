"""Higgsfield REST adapter (INTEGRATIONS.md B2-B5). Thin httpx client, not the SDK: the SDK
retries billable POSTs without an Idempotency-Key. Here a POST is only retried (on 429) with the same key.

Edge mode talks to http://higgsfield.internal (the Worker injects auth). Local mode talks to
api.higgsfield.ai with `Authorization: Key <id:secret>`. The key is never logged or put in errors.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx

from ugecy.integrations.media.catalog import catalog_models
from ugecy.interfaces import MediaJob
from ugecy.settings import Settings

EDGE_UPLOAD_UNSUPPORTED = ("Product photo upload is not available on the deployed app yet: the Worker must relay the "
                           "upload to Higgsfield storage. It works when the agent runs locally.")
_MAX_RETRY_WAIT_S = 30.0
_ATTEMPTS = 3
_STATUSES = {"queued", "in_progress", "completed", "failed", "nsfw", "canceled"}


_HINTS = {
    401: "credentials rejected: check the Higgsfield key",
    403: "insufficient Higgsfield balance (or key expired): top up at console.higgsfield.ai, then retry",
    404: "model or request not found for this account",
    423: "this model is blocked for the account",
    503: "model not ready, try again shortly or pick another model",
}


class HiggsfieldError(RuntimeError):
    """Message is agent-readable: it becomes a tool error, never a stack trace."""

    def __init__(self, status: int, detail: str, correlation_id: str | None = None, retry_after: float | None = None):
        hint = _HINTS.get(status)
        if status == 422:
            hint = "request rejected (validation), fix the arguments: " + detail
        elif status == 429:
            hint = f"account queue full (account_queue_full): wait ~{int(retry_after or 30)} s, then retry; do not resubmit in a loop"
        super().__init__(f"higgsfield HTTP {status}: {hint or detail}" + (f" [{detail}]" if hint and status in _HINTS else "")
                         + (f" (correlation {correlation_id})" if correlation_id else ""))
        self.status, self.retry_after = status, retry_after


def map_outputs(body: dict[str, Any], expires_at: str | None = None) -> list[dict[str, str]]:
    """images[] / video / audio (+ audios[]) -> [{url, kind, expires_at?}]. Provider URLs die after 7 days."""
    outs = [{"url": i["url"], "kind": "image"} for i in body.get("images") or [] if i.get("url")]
    for key, kind in (("video", "video"), ("audio", "audio")):
        if isinstance(body.get(key), dict) and body[key].get("url"):
            outs.append({"url": body[key]["url"], "kind": kind})
    if not any(o["kind"] == "audio" for o in outs):
        outs += [{"url": a["url"], "kind": "audio"} for a in body.get("audios") or [] if a.get("url")][:1]
    return [{**o, "expires_at": expires_at} if expires_at else o for o in outs]


def _detail(resp: httpx.Response) -> str:
    try:
        d = resp.json().get("detail", resp.text)
    except Exception:  # noqa: BLE001
        return resp.text[:200]
    if isinstance(d, dict):
        return str(d.get("message") or d)[:200]
    if isinstance(d, list):  # FastAPI validation: [{loc, msg}]
        return "; ".join(f"{'.'.join(map(str, e.get('loc', [])[1:]))}: {e.get('msg')}" if isinstance(e, dict) else str(e) for e in d)[:300]
    return str(d)[:200]


def _retry_after(resp: httpx.Response) -> float | None:
    try:
        return float(resp.headers["Retry-After"])
    except (KeyError, ValueError):
        try:
            return float(resp.json()["detail"]["retry_after_seconds"])
        except Exception:  # noqa: BLE001
            return None


_RES = r"(480p|720p|1080p|1k|2k|4k)"


def parse_estimate(body: dict[str, Any], args: dict[str, Any]) -> float | None:
    """POST /estimate answers {type:"estimate", usd:"0.004"} for fixed-price models, but token/second-metered models
    (Seedance, Wan, Ads Studio) answer {type:"description", pricing_description:"..."} with no usd: derive from the
    per-second rate for the requested resolution when the text states one, else None (price unknown)."""
    if body.get("usd") not in (None, ""):
        return float(body["usd"])
    text = str(body.get("pricing_description") or "")
    res = str(args.get("resolution") or "720p").lower()
    rates: dict[str, float] = {}
    if "per second" in text:  # "$0.2056 per second of generated video at 480p, $0.4622 at 720p, and $1.1372 at 1080p"
        for usd, r in re.findall(rf"\$(\d+(?:\.\d+)?)(?: per second[^$]*?)?\s+at\s+{_RES}", text, re.IGNORECASE):
            rates.setdefault(r.lower(), float(usd))
    if not rates:  # "480p $0.05, 720p $0.10, or 1080p $0.20" (per generated second)
        for r, usd in re.findall(rf"{_RES}\s*:?\s*\$(\d+(?:\.\d+)?)", text, re.IGNORECASE):
            rates.setdefault(r.lower(), float(usd))
    # shortcut: video-input surcharge (reference-to-video with video_urls) and 16:9 vs 9:16 pixel differences are ignored
    return round(rates[res] * float(args.get("duration") or 5), 4) if res in rates else None


class HiggsfieldProvider:
    name = "higgsfield"
    mode = "live"

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        edge = settings.internal_mode == "edge"
        headers: dict[str, str] = {}
        if not edge:
            key = settings.higgsfield_key
            if not key:
                raise RuntimeError("Higgsfield key missing (set HF_KEY or HF_API_KEY_SECRET) or set media_provider=off")
            headers["Authorization"] = f"Key {key}"
        self._edge, self._transport = edge, transport
        self._client = httpx.AsyncClient(
            base_url="http://higgsfield.internal" if edge else "https://api.higgsfield.ai",
            headers=headers, timeout=30.0, transport=transport,
        )

    async def upload(self, data: bytes, content_type: str) -> str:
        """Upload an input file (a product photo) and return the public URL models can read.
        Step 1 asks Higgsfield for a presigned URL; step 2 PUTs the bytes to storage with a separate client that
        carries no Higgsfield credentials (the docs forbid sending them to the presigned host)."""
        if self._edge:
            # The container has no internet: only *.internal hosts pass the Worker's EgressGateway, and the presigned
            # storage host is not one of them, so the Worker would have to relay this upload.
            raise RuntimeError(EDGE_UPLOAD_UNSUPPORTED)
        meta = (await self._request("POST", "/files/generate-upload-url", json={"content_type": content_type})).json()
        headers = {str(k): str(v) for k, v in (meta.get("upload_headers") or {}).items()}
        headers.setdefault("Content-Type", content_type)
        async with httpx.AsyncClient(timeout=120.0, transport=self._transport) as storage:
            resp = await storage.put(meta["upload_url"], content=data, headers=headers)
        if resp.status_code >= 400:
            raise RuntimeError(f"upload to Higgsfield storage failed: HTTP {resp.status_code}")
        return str(meta["public_url"])

    def models(self, kind: str | None = None) -> list[dict[str, Any]]:
        return catalog_models(kind)

    async def _request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        for attempt in range(_ATTEMPTS):
            resp = await self._client.request(method, path, **kw)
            if resp.status_code == 429 and attempt < _ATTEMPTS - 1:
                # retrying a POST here is safe: callers always send the same Idempotency-Key
                await asyncio.sleep(min(max(_retry_after(resp) or 2.0, 0.0), _MAX_RETRY_WAIT_S))
                continue
            if resp.status_code >= 400:
                raise HiggsfieldError(resp.status_code, _detail(resp), resp.headers.get("X-Correlation-ID"), _retry_after(resp))
            return resp
        raise AssertionError("unreachable")

    async def estimate(self, model: str, args: dict[str, Any]) -> float | None:
        try:
            return parse_estimate((await self._request("POST", f"/estimate/{model}", json=args)).json(), args)
        except (HiggsfieldError, httpx.HTTPError, ValueError, TypeError, AttributeError):
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
            outputs=map_outputs(payload, body.get("expires_at")) if status == "completed" else [],
            error=str(body["error"])[:300] if body.get("error") else ("blocked by content moderation" if status == "nsfw" else None),
        )

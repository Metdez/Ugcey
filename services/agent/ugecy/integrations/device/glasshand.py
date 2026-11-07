"""Glasshand REST provider (contract: packages/contracts/GLASSHAND.md section 3). REST only.

Edge mode: http://glasshand.internal/v1 (Worker injects the stored device-flow bearer).
Local mode: https://api.glasshand.com/v1 with a bearer from settings.glasshand_token (env GLASSHAND_TOKEN, dev only).
"""
from __future__ import annotations

import io
from typing import Any
from uuid import uuid4

import httpx
from PIL import Image

from ugecy.contracts import DeviceInfo
from ugecy.integrations.device import vision
from ugecy.settings import Settings

_USABLE = {"active", "grace"}
_ASCII_OK = set(map(chr, range(32, 127))) | {"\n", "\t"}
EDGE_URL = "http://glasshand.internal/v1"
LOCAL_URL = "https://api.glasshand.com/v1"


def _unit(*vals: Any) -> bool:
    return all(isinstance(v, int | float) and not isinstance(v, bool) and 0 <= v <= 1 for v in vals)


def map_action(a: dict[str, Any]) -> dict[str, Any]:
    """Agent action -> Glasshand Input. Raises ValueError (message = error code) on invalid input."""
    t = a.get("type")
    if t == "tap":
        if not _unit(a.get("x"), a.get("y")):
            raise ValueError("invalid_coordinates")
        return {"type": "click", "x": a["x"], "y": a["y"]}
    if t == "swipe":
        k = ("from_x", "from_y", "to_x", "to_y")
        if not _unit(*(a.get(i) for i in k)):
            raise ValueError("invalid_coordinates")
        return {"type": "drag", "fromX": a["from_x"], "fromY": a["from_y"], "toX": a["to_x"], "toY": a["to_y"],
                "durationMs": int(min(3000, max(100, a.get("duration_ms", 400))))}
    if t == "type":
        text = a.get("text")
        if not isinstance(text, str) or len(text) > 512 or not set(text) <= _ASCII_OK:
            raise ValueError("invalid_text")
        return {"type": "text", "text": text}
    if t == "home":
        return {"type": "home"}
    raise ValueError("unsupported_action")


class GlasshandProvider:
    name = "glasshand"
    mode = "live"

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None, vision_model: Any = None):
        self._settings = settings
        edge = settings.internal_mode == "edge"
        headers = {}
        if not edge:
            if not settings.glasshand_token:
                raise RuntimeError("GLASSHAND_TOKEN missing; connect Glasshand or use device_provider=mock")
            headers["Authorization"] = f"Bearer {settings.glasshand_token}"
        self._client = httpx.AsyncClient(base_url=EDGE_URL if edge else LOCAL_URL, headers=headers, timeout=30.0, transport=transport)
        self._geometry: dict[str, dict[str, Any]] = {}
        self._vision = vision_model

    async def list_devices(self) -> list[DeviceInfo]:
        resp = await self._client.get("/rentals")
        resp.raise_for_status()
        return [DeviceInfo(id=r["id"], name=r.get("name") or r["id"], kind=r.get("kind", "iphone"), status=r.get("status", ""),
                           ready=bool(r.get("deviceReady")) and r.get("status") in _USABLE)
                for r in resp.json().get("items", [])]

    async def _geom(self, device_id: str) -> dict[str, Any]:
        if device_id not in self._geometry:
            conn = await self._client.get(f"/rentals/{device_id}/connection")
            conn.raise_for_status()
            self._geometry[device_id] = conn.json()["geometry"]
        return self._geometry[device_id]

    async def screenshot(self, device_id: str) -> bytes:
        geo = await self._geom(device_id)
        resp = await self._client.get(f"/rentals/{device_id}/screenshot")  # 503 = capture stale; caller retries
        resp.raise_for_status()
        return vision.to_jpeg(vision.crop_viewport(Image.open(io.BytesIO(resp.content)), geo))

    async def describe(self, device_id: str) -> str:
        if self._vision is None:
            from ugecy.llm.workers_ai import make_model

            self._vision = make_model("vision", self._settings)
        return await vision.describe_jpeg(self._vision, await self.screenshot(device_id))

    async def observe(self, device_id: str) -> dict[str, Any]:
        if self._vision is None:
            from ugecy.llm.workers_ai import make_model

            self._vision = make_model("vision", self._settings)
        return await vision.observe_jpeg(self._vision, await self.screenshot(device_id))

    async def send(self, device_id: str, action: dict[str, Any], *, idempotency_key: str | None = None) -> dict[str, Any]:
        try:
            body_in = map_action(action)
        except ValueError as e:
            return {"request_id": "", "ok": False, "error": str(e), "error_code": str(e)}
        # fresh key per input; never replay after an ambiguous failure (network errors propagate to the caller)
        resp = await self._client.post(f"/rentals/{device_id}/input", json=body_in,
                                       headers={"Idempotency-Key": (idempotency_key or uuid4().hex)[:128]})
        try:
            body = resp.json() if resp.content else {}
        except ValueError:
            body = {}
        body = body if isinstance(body, dict) else {}
        err = (body.get("error") or {}).get("code") if isinstance(body.get("error"), dict) else None
        err = err or (f"http_{resp.status_code}" if resp.status_code >= 400 else None)
        if err is None and body.get("ok") is False:
            err = "failed"
        return {"request_id": body.get("requestId", ""), "ok": err is None, "error": err, "error_code": err}  # control_taken / control_busy

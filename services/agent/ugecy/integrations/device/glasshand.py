"""Glasshand REST provider (INTEGRATIONS.md A2-A4). REST only.

Edge mode: http://glasshand.internal (Worker injects the stored device-flow bearer).
Local mode: https://api.glasshand.com with a bearer from env GLASSHAND_TOKEN.
shortcut: live frame stream relay (WebSocket) and device-flow auth are v2; rentals are operator-managed in the
Glasshand dashboard, so this provider only lists/reads them. Upgrade when the Settings UI connects accounts.
"""
from __future__ import annotations

import io
import os
from typing import Any

import httpx
from PIL import Image

from ugecy.contracts import DeviceInfo
from ugecy.settings import Settings

_USABLE = {"active", "grace"}


class GlasshandProvider:
    name = "glasshand"
    mode = "live"

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        edge = settings.internal_mode == "edge"
        headers = {}
        if not edge:
            if not (token := os.environ.get("GLASSHAND_TOKEN")):
                raise RuntimeError("GLASSHAND_TOKEN missing; connect Glasshand or use device_provider=mock")
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(base_url="http://glasshand.internal" if edge else "https://api.glasshand.com",
                                         headers=headers, timeout=30.0, transport=transport)
        self._geometry: dict[str, dict[str, Any]] = {}

    async def list_devices(self) -> list[DeviceInfo]:
        resp = await self._client.get("/rentals")
        resp.raise_for_status()
        return [DeviceInfo(id=r["id"], name=r.get("name") or r["id"], kind=r.get("kind", "iphone"), status=r["status"], ready=True)
                for r in resp.json().get("items", []) if r.get("deviceReady") and r.get("status") in _USABLE]

    async def screenshot(self, device_id: str) -> bytes:
        if device_id not in self._geometry:
            conn = await self._client.get(f"/rentals/{device_id}/connection")
            conn.raise_for_status()
            self._geometry[device_id] = conn.json()["geometry"]
        resp = await self._client.get(f"/rentals/{device_id}/screenshot")  # 503 = capture stale; caller retries
        resp.raise_for_status()
        vp = self._geometry[device_id]["viewport"]
        img = Image.open(io.BytesIO(resp.content)).convert("RGB").crop((vp["x"], vp["y"], vp["x"] + vp["width"], vp["y"] + vp["height"]))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        return buf.getvalue()

    async def describe(self, device_id: str) -> str:
        return "Live Glasshand iPhone: no accessibility tree is available. Use device_screenshot with a vision model; coordinates are normalized 0..1."

    @staticmethod
    def _input(a: dict[str, Any]) -> dict[str, Any]:
        t = a.get("type")
        if t == "tap":
            return {"type": "click", "x": a["x"], "y": a["y"]}
        if t == "swipe":
            return {"type": "drag", "fromX": a["from_x"], "fromY": a["from_y"], "toX": a["to_x"], "toY": a["to_y"], "durationMs": 400}
        if t == "type":
            return {"type": "text", "text": a["text"]}
        if t == "home":
            return {"type": "home"}
        raise ValueError(f"unsupported action {t!r}")

    async def send(self, device_id: str, action: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        resp = await self._client.post(f"/rentals/{device_id}/input", json=self._input(action),
                                       headers={"Idempotency-Key": idempotency_key[:128]})
        body = resp.json() if resp.content else {}
        err = (body.get("error") or {}).get("code") or (f"http_{resp.status_code}" if resp.status_code >= 400 else None)
        if err is None and body.get("ok") is False:
            err = "failed"
        # error "control_taken" means a human took over: callers pause. Never replay on ambiguous failure; re-screenshot.
        return {"request_id": body.get("requestId", ""), "ok": err is None, "error": err}

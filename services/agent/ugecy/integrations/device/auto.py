"""AutoDeviceProvider: real iPhone when Glasshand is connected, otherwise the mock. Never raises on a dead gateway."""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from ugecy.contracts import DeviceInfo
from ugecy.integrations.device.glasshand import GlasshandProvider
from ugecy.integrations.device.mock import DEVICE_ID, MockDeviceProvider
from ugecy.settings import Settings

STATUS_URL = "http://glasshand.internal/_ugecy/status"
TTL_S = 15.0


class AutoDeviceProvider:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None,
                 clock: Callable[[], float] = time.monotonic, vision_model: Any = None):
        self._s, self._transport, self._clock, self._vision = settings, transport, clock, vision_model
        self._mock = MockDeviceProvider(settings)
        self._live: GlasshandProvider | None = None
        self._rental: str | None = None
        self._checked: float | None = None

    @property
    def name(self) -> str:
        return self._live.name if self._live and self._rental else self._mock.name

    @property
    def mode(self) -> str:  # type: ignore[override]
        return "live" if self._live and self._rental else "mock"

    async def _status(self) -> str | None:
        """Selected rental id when Glasshand is usable, else None."""
        if self._s.internal_mode != "edge":
            return self._s.glasshand_rental_id if self._s.glasshand_token else None
        try:
            async with httpx.AsyncClient(timeout=3.0, transport=self._transport) as c:
                r = await c.get(STATUS_URL)
            j = r.json() if r.status_code == 200 else {}
        except (httpx.HTTPError, ValueError):
            return None
        return j.get("selected_rental_id") if j.get("connected") else None

    async def _pick(self, device_id: str | None = None) -> Any:
        now = self._clock()
        if self._checked is None or now - self._checked >= TTL_S:
            self._checked = now
            self._rental = await self._status()
            if self._rental and self._live is None:
                try:
                    self._live = GlasshandProvider(self._s, transport=self._transport, vision_model=self._vision)
                except RuntimeError:
                    self._rental = None
        if device_id == DEVICE_ID or not (self._live and self._rental):
            return self._mock
        return self._live

    async def list_devices(self) -> list[DeviceInfo]:
        p = await self._pick()
        if p is self._mock:
            return await p.list_devices()
        try:
            devs = [d for d in await p.list_devices() if d.id == self._rental and d.ready]
        except httpx.HTTPError:
            devs = []
        if not devs:  # unreachable or rental not ready: fall back, re-check on next call
            self._checked, self._rental = None, None
            return await self._mock.list_devices()
        return devs

    async def screenshot(self, device_id: str) -> bytes:
        return await (await self._pick(device_id)).screenshot(device_id)

    async def describe(self, device_id: str) -> str:
        return await (await self._pick(device_id)).describe(device_id)

    async def send(self, device_id: str, action: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        return await (await self._pick(device_id)).send(device_id, action, idempotency_key=idempotency_key)

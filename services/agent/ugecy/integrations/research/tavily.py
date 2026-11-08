"""Tavily client: search, extract and deep research (POST /research, then poll GET /research/{id}).

Edge: http://tavily.internal (the Worker injects TAVILY_API_KEY); local dev: https://api.tavily.com with the key.
Raw httpx rather than the SDK: the SDK drops to keyless mode without a key (no research) and only accepts 200."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from ugecy.contracts import Mode
from ugecy.integrations.unavailable import TAVILY_OFF, NotConnected

TAVILY_BASE = "https://api.tavily.com"
RETRIES = 5  # transient failures only (network, 429, 434, 5xx): resilience, not a usage budget
POLL_S = 10.0  # Tavily's cookbook polls research every 10 s
_BILLING = {432: "Tavily plan credit limit reached (432): upgrade the plan or wait for the monthly reset",
            433: "Tavily pay-as-you-go spending limit reached (433): raise it in the Tavily dashboard",
            401: "Tavily rejected the API key (401): check the TAVILY_API_KEY Worker secret"}


class TavilyError(RuntimeError):
    """Tavily refused or failed a request; str(e) is safe to show the model."""


def _detail(r: httpx.Response) -> str:
    if r.status_code in _BILLING:
        return _BILLING[r.status_code]
    try:
        body = r.json()
        d = body.get("detail", body.get("error", body))
        msg = d.get("error") or d.get("message") or d if isinstance(d, dict) else d
    except ValueError:
        msg = r.text
    return f"Tavily error {r.status_code}: {str(msg)[:300]}"


def _wait(r: httpx.Response, attempt: int) -> float:
    try:
        return max(0.0, float(r.headers.get("retry-after", "")))
    except ValueError:
        return float(2 ** attempt)


class TavilyClient:
    def __init__(self, settings: Any, http: httpx.AsyncClient | None = None,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self.settings, self._http, self._sleep = settings, http, sleep
        self.edge = settings.internal_mode == "edge"
        configured = settings.has_tavily if self.edge else bool(settings.tavily_api_key)
        self.mode: Mode = "live" if configured else "off"

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            if self.edge:
                from ugecy.internal import client
                self._http = client("tavily.internal", self.settings)
            else:
                self._http = httpx.AsyncClient(base_url=TAVILY_BASE, timeout=180)
        return self._http

    async def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.mode == "off":
            raise NotConnected(TAVILY_OFF)
        auth = None if self.edge else {"Authorization": f"Bearer {self.settings.tavily_api_key}"}  # edge: the Worker adds it
        for attempt in range(RETRIES):
            try:
                r = await self._client().request(method, path, json=body, headers=auth, timeout=180)
            except httpx.TransportError:
                if attempt == RETRIES - 1:
                    raise
                await self._sleep(float(2 ** attempt))
                continue
            if r.is_success:  # includes 202 (research still running)
                return r.json()
            if (r.status_code in (429, 434) or r.status_code >= 500) and attempt < RETRIES - 1:
                await self._sleep(_wait(r, attempt))
                continue
            raise TavilyError(_detail(r))
        raise TavilyError("Tavily request failed")  # unreachable: the last attempt returns or raises

    async def search(self, body: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", "/search", body)

    async def extract(self, body: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", "/extract", body)

    async def research(self, body: dict[str, Any]) -> dict[str, Any]:
        """Start a deep research task and poll it until Tavily reports completed or failed."""
        task = await self.request("POST", "/research", body)
        rid = task.get("request_id")
        if not rid:
            raise TavilyError("Tavily research returned no request_id")
        while True:
            data = await self.request("GET", f"/research/{rid}")
            if data.get("status") in ("completed", "failed"):
                return data
            await self._sleep(POLL_S)

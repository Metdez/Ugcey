"""Dropbox API v2 client. Edge: dropbox.internal (the Worker holds the OAuth tokens). Local: api.dropboxapi.com
with a token refreshed from DROPBOX_APP_KEY/SECRET/REFRESH_TOKEN. Not connected => NotConnected, never fake data."""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any

import httpx

from ugecy.integrations.unavailable import STORAGE_OFF, NotConnected
from ugecy.settings import Settings

EDGE_URL = "http://dropbox.internal"
API_URL = "https://api.dropboxapi.com"
STATUS_TTL_S = 15.0


class DropboxError(RuntimeError):
    def __init__(self, status: int, summary: str, body: Any = None) -> None:
        super().__init__(f"dropbox {status}: {summary}")
        self.status, self.summary, self.body = status, summary, body


class DropboxClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], Any] = asyncio.sleep) -> None:
        self._s, self._transport, self._clock, self._sleep = settings, transport, clock, sleep
        self.edge = settings.internal_mode == "edge"
        self._status: dict[str, Any] | None = None
        self._checked: float | None = None
        self._token: tuple[str, float] | None = None  # local mode only

    # -- status ----------------------------------------------------------
    async def status(self, fresh: bool = False) -> dict[str, Any]:
        """{connected, account_name?, email?, scopes, missing_scopes}; cached 15 s."""
        now = self._clock()
        if not fresh and self._status is not None and self._checked is not None and now - self._checked < STATUS_TTL_S:
            return self._status
        self._checked, self._status = now, await self._fetch_status()
        return self._status

    async def _fetch_status(self) -> dict[str, Any]:
        off = {"connected": False, "scopes": [], "missing_scopes": []}
        if self.edge:
            try:
                async with httpx.AsyncClient(timeout=5.0, transport=self._transport) as c:
                    r = await c.get(f"{EDGE_URL}/_ugecy/status")
                return r.json() if r.status_code == 200 else off
            except (httpx.HTTPError, ValueError):
                return off
        if not (self._s.dropbox_app_key and self._s.dropbox_app_secret and self._s.dropbox_refresh_token):
            return off
        try:
            acct = await self.rpc("/2/users/get_current_account", None)
        except (DropboxError, httpx.HTTPError, NotConnected):
            return off
        return {"connected": True, "account_name": (acct.get("name") or {}).get("display_name"),
                "email": acct.get("email"), "scopes": [], "missing_scopes": []}

    async def connected(self) -> bool:
        return bool((await self.status()).get("connected"))

    # -- transport -------------------------------------------------------
    async def _local_token(self) -> str:
        if self._token and self._token[1] - 60 > self._clock():
            return self._token[0]
        async with httpx.AsyncClient(timeout=30.0, transport=self._transport) as c:
            r = await c.post(f"{API_URL}/oauth2/token", auth=(self._s.dropbox_app_key or "", self._s.dropbox_app_secret or ""),
                             data={"grant_type": "refresh_token", "refresh_token": self._s.dropbox_refresh_token or ""})
        if r.status_code != 200:
            raise NotConnected(STORAGE_OFF)
        j = r.json()
        self._token = (j["access_token"], self._clock() + float(j.get("expires_in", 14400)))
        return self._token[0]

    async def rpc(self, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        """POST a Dropbox RPC endpoint. 429 waits Retry-After and retries; 409 raises DropboxError with the summary."""
        for _ in range(8):
            headers = {"content-type": "application/json"}
            if self.edge:
                url = EDGE_URL + path
            else:
                if not (self._s.dropbox_app_key and self._s.dropbox_app_secret and self._s.dropbox_refresh_token):
                    raise NotConnected(STORAGE_OFF)
                url, headers["authorization"] = API_URL + path, f"Bearer {await self._local_token()}"
            async with httpx.AsyncClient(timeout=60.0, transport=self._transport) as c:
                r = await c.post(url, headers=headers, content=json.dumps(body).encode())  # None -> "null"
            if r.status_code == 429:
                await self._sleep(float(r.headers.get("retry-after") or 5))
                continue
            if r.status_code == 503 and self.edge:
                raise NotConnected(STORAGE_OFF)
            if r.status_code >= 400:
                try:
                    j = r.json()
                except ValueError:
                    j = {"error_summary": r.text[:300]}
                summary = j.get("error_summary") or (j.get("error") or {}).get("message") or r.text[:300]
                raise DropboxError(r.status_code, str(summary), j)
            return r.json() if r.content else {}
        raise DropboxError(429, "rate limited by Dropbox; try again in a minute")

    # -- endpoints -------------------------------------------------------
    async def save_url(self, path: str, url: str) -> dict[str, Any]:
        return await self.rpc("/2/files/save_url", {"path": path, "url": url})

    async def check_job(self, job_id: str) -> dict[str, Any]:
        return await self.rpc("/2/files/save_url/check_job_status", {"async_job_id": job_id})

    async def get_metadata(self, path: str) -> dict[str, Any] | None:
        try:
            return await self.rpc("/2/files/get_metadata", {"path": path})
        except DropboxError as e:
            if e.status == 409 and "not_found" in e.summary:
                return None
            raise

    async def list_folder(self, path: str, limit: int = 100) -> list[dict[str, Any]]:
        try:
            r = await self.rpc("/2/files/list_folder", {"path": path, "recursive": True, "limit": min(limit, 2000)})
        except DropboxError as e:
            if e.status == 409 and "not_found" in e.summary:
                return []
            raise
        entries = list(r.get("entries") or [])
        while r.get("has_more") and len(entries) < limit:
            r = await self.rpc("/2/files/list_folder/continue", {"cursor": r["cursor"]})
            entries += r.get("entries") or []
        return entries[:limit]

    async def temp_link(self, path: str) -> str:
        return (await self.rpc("/2/files/get_temporary_link", {"path": path}))["link"]


_CLIENT: DropboxClient | None = None


def get_dropbox() -> DropboxClient:
    global _CLIENT
    if _CLIENT is None:
        from ugecy.deps import get_deps

        _CLIENT = DropboxClient(get_deps().settings)
    return _CLIENT


def set_dropbox(client: DropboxClient | None) -> None:
    global _CLIENT
    _CLIENT = client

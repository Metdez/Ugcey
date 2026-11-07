"""HTTP client for the Worker's virtual hosts (llm.internal, state.internal, bindings.internal, ...).

Edge mode only: the AgentRuntime DO intercepts these hosts. Local/test mode never calls them
(local fallbacks are implemented per module), so asking for a client there is a bug and raises."""
from __future__ import annotations

from typing import Any

import httpx

from ugecy.settings import Settings, get_settings

_CLIENTS: dict[str, httpx.AsyncClient] = {}


class InternalError(Exception):
    def __init__(self, code: str, message: str, status: int = 0):
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.status = code, message, status


def client(host: str, settings: Settings | None = None) -> httpx.AsyncClient:
    """One shared client per host."""
    if (settings or get_settings()).internal_mode != "edge":
        raise RuntimeError(f"internal host {host!r} is only reachable in UGECY_INTERNAL_MODE=edge")
    if host not in _CLIENTS:
        _CLIENTS[host] = httpx.AsyncClient(base_url=f"http://{host}", timeout=60.0)
    return _CLIENTS[host]


async def post_json(host: str, path: str, body: dict[str, Any], *, http: httpx.AsyncClient | None = None,
                    settings: Settings | None = None) -> dict[str, Any]:
    """POST JSON; non-2xx raises InternalError parsed from the {"error": {code, message}} envelope.
    `http` lets callers (and tests) supply their own client."""
    c = http or client(host, settings)
    r = await c.post(path, json=body)
    if r.is_success:
        return r.json()
    try:
        err = r.json()["error"]
        raise InternalError(str(err.get("code", "error")), str(err.get("message", "")), r.status_code)
    except (ValueError, KeyError, TypeError):
        raise InternalError("http_error", r.text[:200], r.status_code) from None

"""Live research provider: Firecrawl v2 search + oEmbed/Browser Run fetch. Falls back to labelled samples."""
from __future__ import annotations

import contextlib
from typing import Any
from urllib.parse import urlparse

import httpx

from ugecy.contracts import Mode, Source
from ugecy.deps import get_deps
from ugecy.integrations.research.mock import MockResearchProvider

FIRECRAWL_URL = "https://api.firecrawl.dev/v2/search"
MAX_MD = 20_000
OEMBED = {  # Instagram oEmbed needs a Meta app token, so Instagram goes through the browser path.
    "tiktok": "https://www.tiktok.com/oembed",
    "youtube": "https://www.youtube.com/oembed",
}
_DOMAINS = {"tiktok.com": "tiktok", "instagram.com": "instagram", "youtube.com": "youtube",
            "youtu.be": "youtube", "facebook.com": "facebook", "fb.watch": "facebook"}


def platform_of(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower()
    for dom, name in _DOMAINS.items():
        if host == dom or host.endswith("." + dom):
            return name
    return None


class WebResearchProvider:
    name = "web"

    def __init__(self, settings: Any) -> None:
        self.settings = settings
        self.edge = settings.internal_mode == "edge"
        configured = settings.has_firecrawl if self.edge else bool(settings.firecrawl_api_key)
        self.mode: Mode = "live" if configured else "mock"  # fixed at init
        self._mock = MockResearchProvider(settings)

    async def search(self, query: str, platform: str | None = None, limit: int = 8) -> list[Source]:
        if self.mode == "mock":
            return await self._mock.search(query, platform, limit)
        q = f"{query} {platform} short-form video" if platform else query
        body = {"query": q, "limit": limit, "sources": [{"type": "web"}], "domainTools": False}
        try:
            data = await self._post(body)
        except Exception:  # noqa: BLE001  not_configured (503), quota, network: degrade to labelled samples
            return await self._mock.search(query, platform, limit)
        out = []
        for r in (data.get("data") or {}).get("web") or []:
            if r.get("url"):
                out.append(Source(url=r["url"], title=r.get("title") or r["url"], platform=platform_of(r["url"]),
                                  snippet=(r.get("description") or "")[:400] or None))
        return out[:limit]

    async def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        if self.edge:
            from ugecy.internal import post_json  # owned by plan 02-06
            return await post_json("firecrawl.internal", "/v2/search", body)
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(FIRECRAWL_URL, json=body,
                             headers={"Authorization": f"Bearer {self.settings.firecrawl_api_key}"})
            r.raise_for_status()
            return r.json()

    async def fetch(self, url: str) -> dict[str, Any]:
        platform = platform_of(url)
        if url.startswith("https://example.com/sample/"):
            return await self._mock.fetch(url)
        # shortcut: in edge mode external hosts are unreachable from the container, so oEmbed needs an
        # edge route (v2). Until then edge mode uses browser_markdown for every URL.
        if not self.edge and platform in OEMBED:
            with contextlib.suppress(httpx.HTTPError, ValueError):  # else fall through to browser path
                return await self._oembed(url, platform)
        page = await get_deps().edge.browser_markdown(url)
        return {"url": url, "title": page.get("title", ""), "platform": platform,
                "markdown": (page.get("markdown") or "")[:MAX_MD], "metrics": {}}

    async def _oembed(self, url: str, platform: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as c:
            r = await c.get(OEMBED[platform], params={"url": url, "format": "json"})
            r.raise_for_status()
            d = r.json()
        title, author = d.get("title") or "", d.get("author_name") or ""
        md = f"# {title}\n\nAuthor: {author} ({d.get('author_url', '')})\nThumbnail: {d.get('thumbnail_url', '')}\n"
        return {"url": url, "title": title, "platform": platform, "markdown": md[:MAX_MD], "metrics": {}}

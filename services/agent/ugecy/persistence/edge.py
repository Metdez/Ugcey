"""EdgeBindings: EdgeBindingsClient (bindings.internal) and LocalEdgeBindings (httpx / memory / no-ops)."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, ClassVar

import httpx

from ugecy.internal import post_json
from ugecy.settings import Settings

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
MAX_MD = 60_000


class EdgeBindingsClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None):
        self._s, self._http = settings, http

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return await post_json("bindings.internal", path, body, http=self._http, settings=self._s)

    async def browser_markdown(self, url: str) -> dict[str, str]:
        return await self._post("/browser/markdown", {"url": url})

    async def vectors_upsert(self, namespace: str, items: list[dict[str, Any]]) -> int:
        return (await self._post("/vectors/upsert", {"namespace": namespace, "items": items}))["count"]

    async def vectors_query(self, namespace: str, text: str, top_k: int = 5) -> list[dict[str, Any]]:
        return (await self._post("/vectors/query", {"namespace": namespace, "text": text, "top_k": top_k}))["matches"]

    async def media_ingest(self, asset_id: str, url: str, kind: str) -> dict[str, Any]:
        return await self._post("/media/ingest", {"asset_id": asset_id, "url": url, "kind": kind})

    async def schedule_publish(self, post_id: str, publish_at: str | None) -> str:
        return (await self._post("/publish/schedule", {"post_id": post_id, "publish_at": publish_at}))["workflow_id"]

    async def metric(self, event: str, blobs: list[str], doubles: list[float]) -> None:
        await self._post("/metrics", {"event": event, "blobs": blobs, "doubles": doubles})


class _Text(HTMLParser):
    SKIP: ClassVar = {"script", "style", "noscript", "template"}

    def __init__(self) -> None:
        super().__init__()
        self.title, self.parts, self._skip, self._in_title = "", [], 0, False

    def handle_starttag(self, tag, attrs):
        self._skip += tag in self.SKIP
        self._in_title = tag == "title"

    def handle_endtag(self, tag):
        self._skip -= tag in self.SKIP and self._skip > 0
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> tuple[str, str]:
    p = _Text()
    p.feed(html)
    return re.sub(r"\s+", " ", p.title).strip(), re.sub(r"[ \t\r\f\v]*\n\s*", "\n", " ".join(p.parts)).strip()


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"\w+", s.lower()))


class LocalEdgeBindings:
    def __init__(self, settings: Settings | None = None, http: httpx.AsyncClient | None = None):
        self._http = http
        self._vectors: dict[str, dict[str, dict[str, Any]]] = {}

    async def browser_markdown(self, url: str) -> dict[str, str]:
        async with self._http or httpx.AsyncClient(follow_redirects=True) as c:
            r = await c.get(url, headers={"User-Agent": UA}, timeout=15.0)
            r.raise_for_status()
        title, text = html_to_text(r.text)
        return {"url": url, "title": title, "markdown": text[:MAX_MD]}

    async def vectors_upsert(self, namespace: str, items: list[dict[str, Any]]) -> int:
        ns = self._vectors.setdefault(namespace, {})
        for i in items:
            ns[i["id"]] = i
        return len(items)

    async def vectors_query(self, namespace: str, text: str, top_k: int = 5) -> list[dict[str, Any]]:
        # shortcut: token-overlap (Jaccard) instead of embeddings; real vectors come from the edge.
        q = _tokens(text)
        scored = []
        for i in self._vectors.get(namespace, {}).values():
            t = _tokens(i["text"])
            if q & t:
                scored.append({"id": i["id"], "score": len(q & t) / len(q | t), "metadata": i.get("metadata") or {}})
        return sorted(scored, key=lambda m: m["score"], reverse=True)[:top_k]

    async def media_ingest(self, asset_id: str, url: str, kind: str) -> dict[str, Any]:
        return {"asset_id": asset_id, "playback_url": url, "thumbnail_url": None}

    async def schedule_publish(self, post_id: str, publish_at: str | None) -> str:
        return "local-" + post_id  # local mode publishes immediately (tool layer)

    async def metric(self, event: str, blobs: list[str], doubles: list[float]) -> None:
        return None

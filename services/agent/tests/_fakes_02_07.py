"""Fakes for plan 02-07 tests."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from tests._doubles.analytics import MockAnalytics
from tests._doubles.research import MockResearchProvider
from ugecy import deps as deps_mod
from ugecy.contracts import Post, Source
from ugecy.settings import Settings


class FakeApp:
    def __init__(self, posts: list[Post] | None = None) -> None:
        self.sources: list[tuple[str, Source]] = []
        self.posts = posts or []

    async def add_source(self, thread_id: str, source: Source) -> None:
        self.sources.append((thread_id, source))

    async def list_posts(self, thread_id: str | None = None) -> list[Post]:
        return self.posts


class FakeEdge:
    def __init__(self) -> None:
        self.upserts: list[tuple[str, list[dict[str, Any]]]] = []
        self.matches: list[dict[str, Any]] = []

    async def vectors_upsert(self, namespace: str, items: list[dict[str, Any]]) -> int:
        self.upserts.append((namespace, items))
        return len(items)

    async def vectors_query(self, namespace: str, text: str, top_k: int = 5) -> list[dict[str, Any]]:
        return self.matches

    async def browser_markdown(self, url: str) -> dict[str, str]:
        return {"url": url, "title": "T", "markdown": "x" * 30_000}


def install(app: FakeApp | None = None, edge: FakeEdge | None = None):
    s = Settings()
    d = SimpleNamespace(settings=s, app=app or FakeApp(), edge=edge or FakeEdge(),
                        research=MockResearchProvider(s), analytics=MockAnalytics(s))
    deps_mod.set_deps(d)  # type: ignore[arg-type]
    return d

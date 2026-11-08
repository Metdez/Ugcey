"""Labelled sample-pattern research provider. Used when no search key is configured (decision L8)."""
from __future__ import annotations

import re
from typing import Any

from tests._doubles.research_samples import SAMPLES
from ugecy.contracts import Mode, Source

LABEL = "SAMPLE DATA"
_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def _card(row: tuple) -> dict[str, Any]:
    slug, niche, platform, hook, hook_type, fmt, beats, views, er, why = row
    return {
        "label": LABEL, "id": slug, "url": f"https://example.com/sample/{slug}", "title": f"[{LABEL}] {hook}",
        "niche": niche, "platform": platform, "hook": hook, "hook_type": hook_type, "format": fmt,
        "structure": beats, "why_it_works": why,
        "metrics": {"views": views, "er_by_views": er, "note": "illustrative, not measured"},
    }


def search_samples(query: str, platform: str | None = None, limit: int = 8) -> list[dict[str, Any]]:
    """Rank by token overlap with niche/hook/type/format/why. Zero-overlap rows are dropped."""
    q = _tokens(query)
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for i, row in enumerate(SAMPLES):
        if platform and row[2] != platform.lower():
            continue
        card = _card(row)
        hay = _tokens(" ".join([card["niche"], card["hook"], card["hook_type"].replace("_", " "),
                                card["format"].replace("_", " "), card["why_it_works"], " ".join(card["structure"])]))
        score = len(q & hay)
        if score:
            scored.append((-score, i, card))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [c for _, _, c in scored[:limit]]


class FakeResearchProvider:
    name = "fake-research"
    mode: Mode = "live"

    def __init__(self, settings: Any = None) -> None:
        self.settings = settings

    async def search(self, query: str, platform: str | None = None, limit: int = 8, recency: str | None = None,
                     news: bool = False) -> list[Source]:
        return [Source(url=c["url"], title=c["title"], platform=c["platform"],
                       snippet=f"{LABEL} | {c['hook_type']} / {c['format']} | {c['why_it_works']}")
                for c in search_samples(query, platform, limit)]

    async def fetch(self, url: str) -> dict[str, Any]:
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        for row in SAMPLES:
            if row[0] == slug:
                c = _card(row)
                md = (f"# {c['title']}\n\n{LABEL}: illustrative pattern, not a real post.\n\n"
                      f"- Hook type: {c['hook_type']}\n- Format: {c['format']}\n- Niche: {c['niche']}\n\n"
                      "## Beats\n" + "\n".join(f"{n}. {b}" for n, b in enumerate(c["structure"], 1))
                      + f"\n\n## Why it works\n{c['why_it_works']}\n")
                return {"url": url, "title": c["title"], "platform": c["platform"], "markdown": md,
                        "metrics": c["metrics"]}
        return {"url": url, "title": "", "platform": None, "markdown": "", "metrics": {}}

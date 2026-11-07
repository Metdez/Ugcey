"""Deterministic pseudo-metrics seeded by post.id. Mock only; real metrics need platform review (L7)."""
from __future__ import annotations

import hashlib
import random
from typing import Any

from ugecy.contracts import Mode, Post


class FakeAnalytics:
    name = "fake-analytics"
    mode: Mode = "live"

    def __init__(self, settings: Any = None) -> None:
        self.settings = settings

    async def post_metrics(self, posts: list[Post]) -> list[dict[str, Any]]:
        return [self._one(p) for p in posts]

    def _one(self, post: Post) -> dict[str, Any]:
        rng = random.Random(int.from_bytes(hashlib.sha256(post.id.encode()).digest()[:8], "big"))
        views = int(rng.lognormvariate(8.5, 1.1))
        curve = sorted(rng.random() + 0.2 for _ in range(7))  # rising cumulative shape
        total = curve[-1]
        daily = [int(views * c / total) for c in curve]
        return {
            "post_id": post.id, "mode": "live", "views": views,
            "likes": int(views * rng.uniform(0.03, 0.09)), "shares": int(views * rng.uniform(0.004, 0.02)),
            "saves": int(views * rng.uniform(0.005, 0.03)), "watch_time_pct": round(rng.uniform(25, 70), 1),
            "views_7d_cumulative": daily,
        }

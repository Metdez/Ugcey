"""Analytics tool: get_post_metrics."""
from __future__ import annotations

import json

from langchain_core.tools import tool

from ugecy import registry
from ugecy.deps import get_deps
from ugecy.events import current_thread_id


@tool
async def get_post_metrics(post_ids: list[str] | None = None) -> str:
    """Get performance metrics (views, likes, shares, saves, watch-time %, 7-day curve) for posts.

    Use after posts are published or scheduled to compare hooks and formats. Omit `post_ids` for
    all posts in this thread. Output is labelled with its mode: "mock" metrics are simulated and
    must not be presented as real performance.
    """
    deps = get_deps()
    posts = await deps.app.list_posts(current_thread_id())
    if post_ids:
        posts = [p for p in posts if p.id in set(post_ids)]
    if not posts:
        return json.dumps({"mode": deps.analytics.mode, "results": 0, "note": "no matching posts"})
    rows = await deps.analytics.post_metrics(posts)
    return "\n".join([json.dumps({"mode": deps.analytics.mode, "label": "MOCK DATA" if deps.analytics.mode == "mock" else "live",
                                  "results": len(rows)}), *(json.dumps(r) for r in rows)])


registry.register_tool(get_post_metrics, domain="analytics")

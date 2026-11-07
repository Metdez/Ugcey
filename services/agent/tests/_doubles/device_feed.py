"""Mock TikTok-like app for research demos: Spotlight -> For You feed -> search -> results grid -> posts. All data is FAKE."""
from __future__ import annotations

from typing import Any

from PIL import ImageDraw

W, H = 750, 1334
Rect = tuple[float, float, float, float]
BACK: Rect = (0.03, 0.03, 0.25, 0.08)
SEARCH_ICON: Rect = (0.80, 0.03, 0.97, 0.08)
POSTS: list[dict[str, Any]] = [
    {"creator": "@mock.snackqueen", "caption": "3pm slump fix #proteinbar", "overlay": "I stopped buying candy at 3pm", "hook": "I stopped buying candy at 3pm",
     "views": 2_400_000, "likes": 310_000, "comments": 4_200, "shares": 28_000, "saves": 52_000, "audio": "original sound", "format": "problem_solution", "is_ad": False},
    {"creator": "@mock.gymbro_dan", "caption": "ranking 5 protein bars (honest)", "overlay": "#1 will surprise you", "hook": "#1 will surprise you",
     "views": 870_000, "likes": 45_300, "comments": 1_900, "shares": 6_100, "saves": 14_000, "audio": "trending beat", "format": "tutorial_demo", "is_ad": False},
    {"creator": "@mock.brandy.eats", "caption": "my new fave snack #ad", "overlay": "POV: you found the bar that tastes like cookie dough", "hook": "POV: you found the bar that tastes like cookie dough",
     "views": 120_000, "likes": 987, "comments": 64, "shares": 210, "saves": 1_300, "audio": "licensed track", "format": "pov_skit", "is_ad": True},
    {"creator": "@mock.mealprep.jo", "caption": "$2 vs $4 protein bar", "overlay": "Is the $4 bar worth it?", "hook": "Is the $4 bar worth it?",
     "views": 1_200_000, "likes": 98_000, "comments": 3_000, "shares": 11_000, "saves": 33_000, "audio": "original sound", "format": "us_vs_them", "is_ad": False},
]
_TILES: list[Rect] = [(0.05, 0.20, 0.48, 0.46), (0.52, 0.20, 0.95, 0.46), (0.05, 0.50, 0.48, 0.76), (0.52, 0.50, 0.95, 0.76)]
_ACTIONS = [("Like", 0.52), ("Comment", 0.60), ("Share", 0.68)]  # present so the agent sees them; research must never tap them


def fmt(n: int) -> str:
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.1f}K" if n >= 1e4 else str(n)


def title(screen: str, query: str, post: int) -> str:
    return {"spotlight": "Spotlight", "tt_search": "TikTok - Search", "tt_results": f"TikTok - Results: {query or 'protein bar'}",
            "tt_post": f"TikTok - For You ({post + 1}/{len(POSTS)})"}[screen]


def spots(screen: str, query: str) -> list[tuple[str, Rect, str | None]]:
    """Hotspots (label, rect, target) for a feed screen; target 'tt_post:N' opens post N, None = no-op."""
    if screen == "spotlight":
        out: list[tuple[str, Rect, str | None]] = [("Spotlight search field", (0.05, 0.10, 0.95, 0.18), None)]
        return out + ([("TikTok", (0.05, 0.22, 0.95, 0.30), "tt_post:0")] if "tik" in query.lower() else [])
    if screen == "tt_search":
        return [("Back", BACK, "tt_post:0"), ("Search field", (0.05, 0.12, 0.70, 0.20), None), ("Search", (0.72, 0.12, 0.95, 0.20), "tt_results")]
    if screen == "tt_results":
        return [("Back", BACK, "tt_search"), *((f"Result {i + 1}: {p['creator']}", r, f"tt_post:{i}") for i, (p, r) in enumerate(zip(POSTS, _TILES, strict=True)))]
    return [("Back", BACK, "tt_results"), ("Search icon", SEARCH_ICON, "tt_search"),
            *((n, (0.85, y, 0.97, y + 0.06), None) for n, y in _ACTIONS)]


def post_text(i: int) -> str:
    p = POSTS[i]
    m = f"views {fmt(p['views'])}, likes {fmt(p['likes'])}, comments {fmt(p['comments'])}, shares {fmt(p['shares'])}, saves {fmt(p['saves'])}"
    return (f"Post {i + 1}/{len(POSTS)} by {p['creator']}. Caption: \"{p['caption']}\". On-screen text: \"{p['overlay']}\". "
            f"Metrics: {m}. Audio: {p['audio']}." + (" Labelled Sponsored (#ad)." if p["is_ad"] else ""))


def known_post(i: int, els: list[dict[str, Any]]) -> dict[str, Any]:
    """The observe() payload for post i, straight from the known labels (no vision call)."""
    p = POSTS[i]
    return {"platform": "tiktok", "creator": p["creator"], "caption": p["caption"], "on_screen_text": p["overlay"], "hook_guess": p["hook"],
            "metrics": {k: p[k] for k in ("views", "likes", "comments", "shares", "saves")}, "audio": p["audio"], "format_guess": p["format"],
            "is_ad": p["is_ad"], "url": "", "elements": els}


def draw_post(d: ImageDraw.ImageDraw, i: int, font: Any) -> None:
    p = POSTS[i]
    d.rectangle((0, 110, W, H - 70), fill="#0f172a")
    d.text((W / 2, 520), p["overlay"], fill="white", font=font(40), anchor="mm")
    d.text((30, H - 220), p["creator"], fill="white", font=font(34))
    d.text((30, H - 170), p["caption"], fill="#e5e7eb", font=font(28))
    d.text((30, H - 120), f"audio: {p['audio']}", fill="#9ca3af", font=font(24))
    for (name, y), key in zip(_ACTIONS, ("likes", "comments", "shares"), strict=True):
        d.text((W * 0.91, (y + 0.08) * H), f"{name[:1]} {fmt(p[key])}", fill="white", font=font(24), anchor="mm")
    d.text((W * 0.91, 0.86 * H), f"views {fmt(p['views'])}", fill="#9ca3af", font=font(22), anchor="mm")

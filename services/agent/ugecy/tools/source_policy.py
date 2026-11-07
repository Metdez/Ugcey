"""What research may fetch. Public pages a person could open in a browser, one at a time.

Blocks automated search-engine scraping, scraping proxies, unofficial platform APIs/downloaders,
raw media CDNs and platform listing/search pages (bulk scraping is against TikTok/Meta/YouTube terms).
Single public video URLs on those platforms are allowed (the provider reads oEmbed metadata only).
"""
from __future__ import annotations

import time
from urllib.parse import urlparse

# host suffixes that are never fetched
BLOCKED_HOSTS = (
    # search engines (no automated querying; use web_search, which uses a licensed search API)
    "google.com", "bing.com", "duckduckgo.com", "search.brave.com", "mojeek.com", "yandex.com",
    "yandex.ru", "baidu.com", "startpage.com", "ecosia.org", "search.yahoo.com", "qwant.com",
    # scraping proxies, unofficial platform APIs, downloaders, alt-frontends
    "r.jina.ai", "tikwm.com", "snaptik.app", "ssstik.io", "savefrom.net", "tiktokdownload.online",
    "musicaldown.com", "yewtu.be", "invidious.io", "piped.video", "apify.com", "rapidapi.com",
    "scrapingbee.com", "scraperapi.com", "brightdata.com", "zenrows.com",
    # raw media CDNs
    "tiktokcdn.com", "tiktokcdn-us.com", "cdninstagram.com", "fbcdn.net", "googlevideo.com", "ytimg.com",
)
# (host suffix, path prefixes) listing/search pages on social platforms
BLOCKED_PATHS = {
    "tiktok.com": ("/search", "/tag/", "/discover", "/oembed", "/api/", "/embed/", "/player/", "/node/"),
    "youtube.com": ("/results", "/feed", "/api/", "/youtubei/"),
    "instagram.com": ("/explore", "/api/", "/graphql"),
    "facebook.com": ("/search", "/api/", "/graphql"),
}
FETCH_BUDGET = 12  # fetch_page calls per thread per window
WINDOW_S = 15 * 60
_calls: dict[str, list[float]] = {}


def _match(host: str, suffix: str) -> bool:
    return host == suffix or host.endswith("." + suffix)


def policy_error(url: str) -> str | None:
    p = urlparse(url)
    host = (p.hostname or "").lower().rstrip(".")
    if any(_match(host, h) for h in BLOCKED_HOSTS):
        return ("blocked source: search engines, scraping proxies, unofficial platform APIs and media CDNs "
                "are not permitted. Use web_search, pages the operator provided, or your own knowledge.")
    for suffix, prefixes in BLOCKED_PATHS.items():
        if _match(host, suffix) and (p.path.startswith(prefixes) or (suffix == "tiktok.com" and _is_profile(p.path))):
            return ("blocked: platform search, tag, profile and feed pages can't be scraped. "
                    "Fetch individual public post URLs only.")
    return None


def _is_profile(path: str) -> bool:
    parts = [x for x in path.split("/") if x]
    return len(parts) == 1 and parts[0].startswith("@")


def take_budget(thread_id: str | None) -> str | None:
    """Consume one fetch for the thread; return an error once the window budget is spent."""
    key = thread_id or "_"
    now = time.monotonic()
    recent = [t for t in _calls.get(key, []) if now - t < WINDOW_S]
    if len(recent) >= FETCH_BUDGET:
        _calls[key] = recent
        return (f"fetch budget reached ({FETCH_BUDGET} pages per {WINDOW_S // 60} min for this thread). "
                "Work with what you have and write your findings now.")
    _calls[key] = [*recent, now]
    return None

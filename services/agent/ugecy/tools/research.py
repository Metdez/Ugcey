"""Research tools: web_search, fetch_page. Public, permitted pages only."""
from __future__ import annotations

import ipaddress
import json
from urllib.parse import urlparse

from langchain_core.tools import tool

from ugecy import registry
from ugecy.contracts import Source
from ugecy.deps import get_deps
from ugecy.events import current_thread_id, emit
from ugecy.tools.source_policy import policy_error, take_budget

_BLOCKED_SUFFIXES = (".internal", ".local", ".localhost", ".lan", ".home.arpa")


def check_public_url(url: str) -> str | None:
    """Return an error string if url is not a public http(s) URL, else None."""
    try:
        p = urlparse(url.strip())
        host = (p.hostname or "").lower().rstrip(".")
    except ValueError:
        return "invalid URL"
    if p.scheme not in ("http", "https") or not host:
        return "only http(s) URLs are allowed"
    if p.username or p.password:
        return "URLs with credentials are not allowed"
    if host == "localhost" or host.endswith(_BLOCKED_SUFFIXES) or "." not in host and ":" not in host:
        return "private or internal hosts are not allowed"
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return None
    if not ip.is_global:
        return "private or internal addresses are not allowed"
    # shortcut: no DNS resolution check (a public name pointing at a private IP); the fetch itself runs
    # at the edge (Browser Run), which has no private network. Add resolve-and-pin if fetching locally.
    return None


async def _record(source: Source) -> None:
    emit("source.added", source=source.model_dump())
    tid = current_thread_id()
    if tid:
        await get_deps().app.add_source(tid, source)


@tool
async def web_search(query: str, platform: str | None = None, limit: int = 8) -> str:
    """Search the public web for UGC ads, short-form video patterns, competitor pages, reviews or trends.

    Use this first when you need examples, hooks, formats or market context. `platform` may be
    tiktok, instagram, youtube or facebook to bias results. Returns one JSON object per line
    (url, title, platform, snippet). Only public, permitted pages are searched; never use it to
    reach logged-in, private or paywalled content. If results are labelled SAMPLE DATA the
    provider is in mock mode: treat them as illustrative patterns, not real posts.
    """
    limit = max(1, min(limit, 15))
    research = get_deps().research
    sources = await research.search(query, platform, limit)
    for s in sources:
        await _record(s)
    if not sources:
        return json.dumps({"mode": research.mode, "results": 0, "note": "no results; try broader terms"})
    meta: dict[str, object] = {"mode": research.mode, "results": len(sources)}
    if research.mode == "mock":
        meta["note"] = ("SAMPLE DATA ONLY: live web search is not configured (no FIRECRAWL_API_KEY). Do not try "
                        "to search by fetching search engines or scraping platforms. Use these samples, pages the "
                        "operator gave you and your own expertise, and tell the operator search is in sample mode.")
    head = json.dumps(meta)
    return "\n".join([head, *(json.dumps(s.model_dump(exclude_none=True)) for s in sources)])


@tool
async def fetch_page(url: str) -> str:
    """Fetch one public web page (or a TikTok/YouTube link card) and return its readable text.

    Use this to read a page the operator pasted or a result from web_search: product pages,
    reviews, blogs, competitor sites, or a video link for title/author. Only public pages the
    operator is permitted to view; private, login-gated, internal or local addresses are refused.
    Returns metadata JSON then the first 8000 characters of markdown.
    """
    err = check_public_url(url) or policy_error(url) or take_budget(current_thread_id())
    if err:
        return json.dumps({"error": err, "url": url})
    try:
        page = await get_deps().research.fetch(url)
    except Exception as e:  # noqa: BLE001 tool errors go back to the model, not up the stack
        return json.dumps({"error": f"fetch failed: {type(e).__name__}", "url": url})
    await _record(Source(url=url, title=page.get("title") or url, platform=page.get("platform")))
    meta = {k: page.get(k) for k in ("url", "title", "platform", "metrics")}
    return json.dumps(meta) + "\n\n" + (page.get("markdown") or "")[:8000]


registry.register_tool(web_search, domain="research")
registry.register_tool(fetch_page, domain="research")

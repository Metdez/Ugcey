"""Deep research tools (Tavily, internal only): deep_search, read_pages, deep_research.

No Ugecy budget: only Tavily's own per-request maxima (20 results, 20 URLs) apply. Off -> mode "off" + what to connect."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from langchain_core.tools import tool

from ugecy import registry
from ugecy.contracts import Source
from ugecy.deps import get_deps
from ugecy.integrations.research.tavily import TavilyClient
from ugecy.integrations.research.web import platform_of
from ugecy.integrations.unavailable import NotConnected
from ugecy.tools.research import _record, check_public_url
from ugecy.tools.source_policy import policy_error

PAGE_CHARS = 20_000  # per extracted page, the same as fetch_page; keeps one call inside the model's context


def _client() -> TavilyClient:  # tests replace this
    return TavilyClient(get_deps().settings)


def _fail(c: TavilyClient, e: Exception, what: str) -> str:
    if isinstance(e, NotConnected):
        return json.dumps({"mode": "off", "error": str(e)})
    return json.dumps({"mode": c.mode, "error": f"{what} failed: {e}"})  # reported, never substituted


async def _source(url: str, title: str | None, snippet: str | None = None) -> None:
    await _record(Source(url=url, title=title or url, platform=platform_of(url), snippet=(snippet or "")[:400] or None))


@tool
async def deep_search(query: str, topic: str = "general", time_range: str | None = None, max_results: int = 20,
                        include_domains: list[str] | None = None, exclude_domains: list[str] | None = None) -> str:
    """Deep web search (advanced depth): the most relevant passages from each result, not just snippets.

    Run many of these, in parallel, from different angles. `topic` is general or news (news adds publish
    dates). `time_range` is day, week, month or year; use week or month for what is working now.
    `max_results` up to 20. `include_domains` focuses on chosen sites (e.g. reddit.com for real customer
    language, tiktok.com for trend snippets). Returns one JSON object per line: url, title, published_date,
    score, content. Follow up with read_pages on the best URLs.
    """
    c = _client()
    body: dict[str, Any] = {"query": query, "search_depth": "advanced", "chunks_per_source": 3,
                            "max_results": max(1, min(max_results, 20)), "topic": topic}
    for k, v in (("time_range", time_range), ("include_domains", include_domains), ("exclude_domains", exclude_domains)):
        if v:
            body[k] = v
    try:
        data = await c.search(body)
    except Exception as e:  # noqa: BLE001 tool errors go back to the model
        return _fail(c, e, "deep search")
    results = [r for r in data.get("results") or [] if r.get("url")]
    for r in results:
        await _source(r["url"], r.get("title"), r.get("content"))
    head = json.dumps({"mode": c.mode, "results": len(results), "query": query})
    keep = ("url", "title", "published_date", "score", "content")
    return "\n".join([head, *(json.dumps({k: r[k] for k in keep if r.get(k) is not None}) for r in results)])


@tool
async def read_pages(urls: list[str], query: str | None = None) -> str:
    """Read the full text of public pages (advanced extraction handles JS-heavy pages and tables).

    Pass up to dozens of URLs (sent in groups of 20, in parallel). With `query`, each page returns the
    passages most relevant to it. Platform search, tag and profile pages, logins and private hosts are
    refused, as with fetch_page. Returns one JSON object per page: url, content (up to 20,000 chars), or error.
    """
    c = _client()
    ok, refused = [], []
    for u in urls:
        err = check_public_url(u) or policy_error(u)
        if err:
            refused.append({"url": u, "error": err})
        else:
            ok.append(u)
    base: dict[str, Any] = {"extract_depth": "advanced", "format": "markdown"}
    if query:
        base |= {"query": query, "chunks_per_source": 5}
    try:
        parts = await asyncio.gather(*(c.extract({**base, "urls": ok[i:i + 20]}) for i in range(0, len(ok), 20)))
    except Exception as e:  # noqa: BLE001
        return _fail(c, e, "page reading")
    pages = [r for p in parts for r in p.get("results") or [] if r.get("url")]
    failed = [*refused, *({"url": f.get("url"), "error": f.get("error")} for p in parts for f in p.get("failed_results") or [])]
    for r in pages:
        await _source(r["url"], None, r.get("raw_content"))
    head = json.dumps({"mode": c.mode, "pages": len(pages), "failed": len(failed)})
    return "\n".join([head, *(json.dumps({"url": r["url"], "content": (r.get("raw_content") or "")[:PAGE_CHARS]})
                              for r in pages), *(json.dumps(f) for f in failed)])


@tool
async def deep_research(question: str, model: str = "pro", include_domains: list[str] | None = None,
                          exclude_domains: list[str] | None = None) -> str:
    """Run a deep research task: it plans, searches many sources and writes a long cited report.

    Takes minutes. Start several at once on different angles (e.g. winning hooks in the niche right now,
    winning short-form formats and structures, what customers say and complain about, competitor ads)
    and keep working while they run. Give the question full context: product, audience, platforms, time
    window and the output you want (e.g. "a table of hook patterns with examples, why each works and
    source URLs"). `model` pro (multi-angle, default) or mini (narrow, faster). Returns the report and its sources.
    """
    c = _client()
    body: dict[str, Any] = {"input": question, "model": model, "output_length": "long", "citation_format": "numbered"}
    for k, v in (("include_domains", include_domains), ("exclude_domains", exclude_domains)):
        if v:
            body[k] = v[:20]  # Tavily's per-request maximum
    try:
        data = await c.research(body)
    except Exception as e:  # noqa: BLE001
        return _fail(c, e, "deep research")
    if data.get("status") != "completed":
        return json.dumps({"mode": c.mode, "status": data.get("status"), "error": "deep research task failed"})
    sources = [s for s in data.get("sources") or [] if s.get("url")]
    for s in sources:
        await _source(s["url"], s.get("title"))
    content = data.get("content")
    report = content if isinstance(content, str) else json.dumps(content, indent=1)
    refs = "\n".join(f"[{i}] {s.get('title') or s['url']} - {s['url']}" for i, s in enumerate(sources, 1))
    return json.dumps({"mode": c.mode, "status": "completed", "sources": len(sources)}) + f"\n\n{report}\n\nSources:\n{refs}"


registry.register_tool(deep_search, domain="research")
registry.register_tool(read_pages, domain="research")
registry.register_tool(deep_research, domain="research")

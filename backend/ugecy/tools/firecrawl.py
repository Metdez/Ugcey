"""Firecrawl web research tools for Ugecy agents.

The API key is read from ``FIRECRAWL_API`` (``FIRECRAWL_API_KEY`` also works) and
never leaves the client. Every tool call is written to the ``ugecy.audit`` logger
with its arguments, status, and duration so research stays auditable.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, TypeVar

from firecrawl import Firecrawl
from langchain_core.tools import BaseTool, StructuredTool, ToolException

ENV_KEYS = ("FIRECRAWL_API", "FIRECRAWL_API_KEY")
MAX_SCRAPE_CHARS = 20_000
MAX_SEARCH_RESULTS = 10
MAX_MAP_LINKS = 200

audit_log = logging.getLogger("ugecy.audit")
T = TypeVar("T")


def make_client(api_key: str | None = None) -> Firecrawl:
    """Build a Firecrawl client from an explicit key or the environment."""
    key = api_key or next((os.environ[k] for k in ENV_KEYS if os.environ.get(k)), None)
    if not key:
        raise RuntimeError("Firecrawl API key missing: set FIRECRAWL_API in the environment.")
    return Firecrawl(api_key=key)


def _audited(tool: str, args: dict[str, Any], run: Callable[[], T]) -> T:
    """Run one external call and record it, turning failures into tool errors."""
    start = time.monotonic()
    status, error = "ok", None
    try:
        return run()
    except Exception as exc:
        status, error = "error", f"{type(exc).__name__}: {exc}"
        raise ToolException(f"{tool} failed: {error}") from exc
    finally:
        record = {
            "tool": tool,
            "args": args,
            "status": status,
            "duration_ms": round((time.monotonic() - start) * 1000),
        }
        if error:
            record["error"] = error
        audit_log.info("tool_call %s %s", tool, status, extra={"audit": record})


def _clamp(value: int, upper: int) -> int:
    return max(1, min(value, upper))


def _hit(item: Any) -> dict[str, str | None]:
    """Normalize a search hit (plain result or scraped document) to a small dict."""
    meta = getattr(item, "metadata", None)
    return {
        "title": getattr(item, "title", None) or getattr(meta, "title", None),
        "url": getattr(item, "url", None) or getattr(meta, "source_url", None),
        "description": getattr(item, "description", None) or getattr(meta, "description", None),
    }


def firecrawl_tools(client: Firecrawl | None = None) -> list[BaseTool]:
    """Return the Firecrawl search, scrape, and map tools bound to one client."""
    fc = client or make_client()

    def firecrawl_search(query: str, limit: int = 5) -> str:
        """Search the web for current, public sources on a topic.

        Args:
            query: Search query; supports operators such as site:example.com.
            limit: Number of results to return, from 1 to 10.
        """
        limit = _clamp(limit, MAX_SEARCH_RESULTS)

        def run() -> str:
            data = fc.search(query, limit=limit)
            return json.dumps([_hit(r) for r in data.web or []], ensure_ascii=False)

        return _audited("firecrawl_search", {"query": query, "limit": limit}, run)

    def firecrawl_scrape(url: str, only_main_content: bool = True) -> str:
        """Fetch one web page as markdown, with its source URL and retrieval time.

        Args:
            url: Absolute URL of the page to read.
            only_main_content: Drop navigation, headers, and footers when true.
        """

        def run() -> str:
            doc = fc.scrape(url, formats=["markdown"], only_main_content=only_main_content)
            meta = getattr(doc, "metadata", None)
            text = getattr(doc, "markdown", None) or ""
            if len(text) > MAX_SCRAPE_CHARS:
                text = f"{text[:MAX_SCRAPE_CHARS]}\n\n[truncated: first {MAX_SCRAPE_CHARS} of {len(text)} chars]"
            retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
            header = [
                f"Title: {getattr(meta, 'title', None) or 'unknown'}",
                f"Source: {getattr(meta, 'source_url', None) or url}",
                f"Retrieved: {retrieved}",
            ]
            return "\n".join(header) + "\n\n" + text

        return _audited(
            "firecrawl_scrape", {"url": url, "only_main_content": only_main_content}, run
        )

    def firecrawl_map(url: str, search: str | None = None, limit: int = 50) -> str:
        """List the URLs of a website, optionally filtered by a search term.

        Args:
            url: Site root or section to map, such as https://example.com/docs.
            search: Optional term used to rank and filter the returned URLs.
            limit: Maximum number of URLs to return, from 1 to 200.
        """
        limit = _clamp(limit, MAX_MAP_LINKS)

        def run() -> str:
            data = fc.map(url, search=search, limit=limit)
            links = [{"url": getattr(link, "url", link), "title": getattr(link, "title", None)}
                     for link in data.links or []]
            return json.dumps(links, ensure_ascii=False)

        return _audited("firecrawl_map", {"url": url, "search": search, "limit": limit}, run)

    return [
        StructuredTool.from_function(fn, parse_docstring=True, handle_tool_error=True)
        for fn in (firecrawl_search, firecrawl_scrape, firecrawl_map)
    ]

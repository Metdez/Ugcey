import json

import httpx
import pytest

from tests._fakes_02_07 import install
from ugecy.integrations.research.tavily import POLL_S, TavilyClient, TavilyError
from ugecy.integrations.research.web import WebResearchProvider
from ugecy.integrations.unavailable import TAVILY_OFF, NotConnected
from ugecy.settings import Settings
from ugecy.tools import tavily as tools


def tavily(handler, waits: list[float]) -> TavilyClient:
    """Local-mode client over a fake Tavily API (test transport only)."""
    async def sleep(s: float) -> None:
        waits.append(s)
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.tavily.com")
    return TavilyClient(Settings(tavily_api_key="tvly-k"), http=http, sleep=sleep)


async def test_off_without_a_key_says_what_to_connect():
    c = TavilyClient(Settings())
    assert c.mode == "off"
    with pytest.raises(NotConnected, match="TAVILY_API_KEY"):
        await c.search({"query": "x"})
    install()
    assert json.loads(await tools.tavily_search.ainvoke({"query": "x"})) == {"mode": "off", "error": TAVILY_OFF}


async def test_rate_limit_honours_retry_after_and_billing_errors_are_not_retried():
    calls, waits = [], []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.path)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "7"}, json={"detail": {"error": "slow down"}})
        return httpx.Response(200, json={"results": []})

    assert await tavily(handler, waits).search({"query": "hooks"}) == {"results": []}
    assert waits == [7.0] and calls == ["/search", "/search"]
    billing = tavily(lambda r: httpx.Response(432, json={"detail": {"error": "limit"}}), waits := [])
    with pytest.raises(TavilyError, match="432"):
        await billing.search({"query": "x"})
    assert waits == []


async def test_research_starts_a_task_and_polls_until_completed():
    seen, waits = [], []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append((req.method, req.url.path, req.headers.get("authorization")))
        if req.method == "POST":
            assert json.loads(req.content)["input"] == "winning serum hooks"
            return httpx.Response(201, json={"request_id": "r1", "status": "pending"})
        if len([s for s in seen if s[0] == "GET"]) == 1:
            return httpx.Response(202, json={"request_id": "r1", "status": "in_progress"})
        return httpx.Response(200, json={"status": "completed", "content": "REPORT",
                                         "sources": [{"title": "A", "url": "https://a.example/x"}]})

    out = await tavily(handler, waits).research({"input": "winning serum hooks", "model": "pro"})
    assert out["content"] == "REPORT" and waits == [POLL_S]
    assert [s[:2] for s in seen] == [("POST", "/research"), ("GET", "/research/r1"), ("GET", "/research/r1")]
    assert all(s[2] == "Bearer tvly-k" for s in seen)


async def test_tools_search_extract_research(monkeypatch):
    from ugecy.tools import research
    d = install()
    monkeypatch.setattr(research, "emit", lambda t, **f: None)
    monkeypatch.setattr(research, "current_thread_id", lambda: "th1")
    bodies = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content) if req.content else {}
        bodies.append((req.url.path, body))
        if req.url.path == "/search":
            return httpx.Response(200, json={"results": [
                {"url": "https://b.example/hooks", "title": "Hooks", "content": "POV hook", "score": 0.9}]})
        if req.url.path == "/extract":
            return httpx.Response(200, json={"results": [{"url": u, "raw_content": "x" * 30_000} for u in body["urls"]],
                                             "failed_results": []})
        if req.method == "POST":
            return httpx.Response(200, json={"request_id": "r9", "status": "pending"})
        return httpx.Response(200, json={"status": "completed", "content": "Hook table",
                                         "sources": [{"title": "S", "url": "https://s.example/1"}]})

    monkeypatch.setattr(tools, "_client", lambda: tavily(handler, []))
    out = (await tools.tavily_search.ainvoke({"query": "serum hooks", "max_results": 50, "time_range": "month"})).splitlines()
    assert json.loads(out[0]) == {"mode": "live", "results": 1, "query": "serum hooks"}
    assert bodies[0][1] | {} == {"query": "serum hooks", "search_depth": "advanced", "chunks_per_source": 3,
                                 "max_results": 20, "topic": "general", "time_range": "month"}

    urls = [f"https://blog.example/{i}" for i in range(25)] + ["https://www.tiktok.com/tag/skincare", "http://localhost/x"]
    out = (await tools.tavily_extract.ainvoke({"urls": urls, "query": "hooks"})).splitlines()
    head = json.loads(out[0])
    assert head == {"mode": "live", "pages": 25, "failed": 2}  # platform tag page and private host refused
    assert [len(b["urls"]) for p, b in bodies if p == "/extract"] == [20, 5]  # Tavily's 20-URL maximum, in parallel
    assert len(json.loads(out[1])["content"]) == tools.PAGE_CHARS

    out = await tools.tavily_research.ainvoke({"question": "winning serum hooks on TikTok right now"})
    assert '"status": "completed"' in out and "Hook table" in out and "[1] S - https://s.example/1" in out
    assert {s.url for _, s in d.app.sources} >= {"https://b.example/hooks", "https://s.example/1"}


async def test_firecrawl_web_search_recency_and_news(monkeypatch):
    p = WebResearchProvider(Settings(firecrawl_api_key="k"))
    sent = []

    async def post(path, body):
        sent.append(body)
        kind = body["sources"][0]["type"]
        return {"data": {kind: [{"url": "https://n.example/a", "title": "N", "snippet": "s", "date": "2 days ago"}]}}

    monkeypatch.setattr(p, "_post", post)
    out = await p.search("ugc hooks", recency="week", news=True)
    assert sent[0]["tbs"] == "sbd:1,qdr:w" and sent[0]["sources"] == [{"type": "news"}]
    assert out[0].url == "https://n.example/a" and out[0].snippet.startswith("2 days ago")

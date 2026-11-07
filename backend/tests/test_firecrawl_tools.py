import json
import logging

import pytest
from firecrawl.v2.types import Document, DocumentMetadata, LinkResult, MapData, SearchData, SearchResultWeb

from ugecy.tools import firecrawl as fc_tools


class FakeFirecrawl:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls: list[tuple[str, dict]] = []

    def search(self, query, **kw):
        self.calls.append(("search", {"query": query, **kw}))
        if self.fail:
            raise RuntimeError("rate limited")
        return SearchData(web=[SearchResultWeb(url="https://a.test", title="A", description="about A")])

    def scrape(self, url, **kw):
        self.calls.append(("scrape", {"url": url, **kw}))
        return Document(markdown="x" * (fc_tools.MAX_SCRAPE_CHARS + 5),
                        metadata=DocumentMetadata(title="Page", source_url=url))

    def map(self, url, **kw):
        self.calls.append(("map", {"url": url, **kw}))
        return MapData(links=[LinkResult(url=f"{url}/docs", title="Docs")])


def tools_by_name(client):
    return {t.name: t for t in fc_tools.firecrawl_tools(client)}


def test_exposes_three_tools_with_documented_args():
    tools = tools_by_name(FakeFirecrawl())
    assert set(tools) == {"firecrawl_search", "firecrawl_scrape", "firecrawl_map"}
    schema = tools["firecrawl_search"].args
    assert set(schema) == {"query", "limit"}
    assert "site:" in schema["query"]["description"]


def test_search_returns_compact_json_and_clamps_limit():
    client = FakeFirecrawl()
    out = tools_by_name(client)["firecrawl_search"].invoke({"query": "ugc hooks", "limit": 99})
    assert json.loads(out) == [{"title": "A", "url": "https://a.test", "description": "about A"}]
    assert client.calls[0][1]["limit"] == fc_tools.MAX_SEARCH_RESULTS


def test_scrape_adds_provenance_and_truncates():
    out = tools_by_name(FakeFirecrawl())["firecrawl_scrape"].invoke({"url": "https://a.test"})
    assert out.startswith("Title: Page\nSource: https://a.test\nRetrieved: ")
    assert "[truncated: first 20000 of 20005 chars]" in out


def test_map_returns_links():
    client = FakeFirecrawl()
    out = tools_by_name(client)["firecrawl_map"].invoke({"url": "https://a.test", "search": "docs"})
    assert json.loads(out) == [{"url": "https://a.test/docs", "title": "Docs"}]
    assert client.calls[0][1]["search"] == "docs"


def test_failures_reach_the_agent_and_are_audited(caplog):
    caplog.set_level(logging.INFO, logger="ugecy.audit")
    out = tools_by_name(FakeFirecrawl(fail=True))["firecrawl_search"].invoke({"query": "q"})
    assert "firecrawl_search failed: RuntimeError: rate limited" in out
    record = caplog.records[-1].audit
    assert record["status"] == "error" and record["args"] == {"query": "q", "limit": 5}


def test_success_is_audited_without_the_key(caplog, monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API", "fc-secret")
    caplog.set_level(logging.INFO, logger="ugecy.audit")
    tools_by_name(FakeFirecrawl())["firecrawl_map"].invoke({"url": "https://a.test"})
    record = caplog.records[-1].audit
    assert record["tool"] == "firecrawl_map" and record["status"] == "ok"
    assert "fc-secret" not in json.dumps(record)


def test_client_reads_firecrawl_api_env(monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    monkeypatch.setenv("FIRECRAWL_API", "fc-from-env")
    assert fc_tools.make_client().api_key == "fc-from-env"


def test_missing_key_fails_clearly(monkeypatch):
    for key in fc_tools.ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError, match="FIRECRAWL_API"):
        fc_tools.make_client()

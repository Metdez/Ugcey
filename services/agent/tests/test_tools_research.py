import json

import pytest

from tests._doubles.analytics import MockAnalytics
from tests._doubles.research import search_samples
from tests._doubles.research_samples import SAMPLES
from tests._fakes_02_07 import FakeApp, FakeEdge, install
from ugecy import registry
from ugecy.contracts import Post
from ugecy.integrations.research.web import WebResearchProvider, platform_of
from ugecy.settings import Settings
from ugecy.tools import analytics, creative, memory, research
from ugecy.tools.creative import run_checks
from ugecy.tools.research import check_public_url


@pytest.fixture(autouse=True)
def _no_stream(monkeypatch):
    # emit() needs a LangGraph run context; outside a run it is a no-op in production
    for mod in (research, memory):
        monkeypatch.setattr(mod, "emit", lambda *a, **k: None)


def test_tool_names_registered():
    for name in ["web_search", "fetch_page", "remember_pattern", "search_patterns", "compliance_check", "get_post_metrics"]:
        assert name in registry.TOOLS
    assert registry.TOOLS["compliance_check"].domain == "creative"


def test_sample_library():
    assert len(SAMPLES) == 24
    assert len({r[0] for r in SAMPLES}) == 24
    assert all(r[0] and r[5] for r in SAMPLES)


def test_mock_search_ranking():
    top = search_samples("supplements magnesium label warning")[0]
    assert top["id"] == "supp-label-warning" and top["url"] == "https://example.com/sample/supp-label-warning"
    assert "SAMPLE DATA" in top["title"]
    assert all(c["platform"] == "youtube" for c in search_samples("food", platform="youtube"))
    assert search_samples("zzzqqq") == []


def test_compliance_blocks_cure_and_weight_loss():
    r = run_checks("This cream cures eczema and you'll lose 10 lbs in 2 weeks, guaranteed!", "tiktok", False, False)
    assert r["verdict"] == "block"
    assert {"health.cure_word", "health.weight_loss", "claim.guaranteed"} <= {i["rule"] for i in r["issues"]}


def test_compliance_clinical_needs_source():
    assert run_checks("Clinically proven formula", "instagram", False, False)["verdict"] == "fix"
    assert run_checks("Clinically proven formula https://x.org/study", "instagram", False, False)["verdict"] == "pass"


def test_compliance_paid_partnership_disclosure():
    assert run_checks("Love this serum", "tiktok", False, True)["verdict"] == "block"
    assert run_checks("#ad Love this serum", "tiktok", False, True)["verdict"] == "pass"
    buried = "x" * 200 + " #ad"
    assert run_checks(buried, "tiktok", False, True)["verdict"] == "fix"


def test_compliance_ai_label_and_fake_testimonial():
    ok = run_checks("Meet the new serum. Hydrates for 24 hours.", "youtube", True, False)
    assert ok["verdict"] == "pass" and any(i["rule"] == "platform.ai_label" for i in ok["issues"])
    bad = run_checks("I tried this for a month and my results are amazing", "tiktok", True, False)
    assert bad["verdict"] == "block" and any(i["rule"] == "ftc.fake_testimonial" for i in bad["issues"])
    assert run_checks("I tried this for a month", "tiktok", False, False)["verdict"] == "pass"


def test_compliance_caption_length_and_tool_json():
    r = run_checks("a" * 2300, "instagram", False, False)
    assert r["verdict"] == "fix"
    out = json.loads(creative.compliance_check.invoke({"text": "hello", "platform": "tiktok", "is_ai_generated": False}))
    assert out["verdict"] == "pass"


def test_url_validation():
    for bad in ["http://localhost/x", "http://169.254.169.254/latest", "http://10.0.0.1", "ftp://example.com",
                "http://[::1]/", "http://foo.internal/", "http://intranet/", "http://user:pw@example.com"]:
        assert check_public_url(bad), bad
    assert check_public_url("https://www.tiktok.com/@a/video/1") is None


async def test_fetch_page_rejects_private():
    install()
    out = json.loads(await research.fetch_page.ainvoke({"url": "http://169.254.169.254/"}))
    assert "error" in out
    out = json.loads(await research.fetch_page.ainvoke({"url": "http://localhost:8000"}))
    assert "error" in out


async def test_fetch_page_truncates_and_records():
    d = install()
    d.research = WebResearchProvider(Settings())  # mock mode, no key -> browser_markdown path
    out = await research.fetch_page.ainvoke({"url": "https://example.org/page"})
    head, body = out.split("\n\n", 1)
    assert json.loads(head)["title"] == "T" and len(body) == 8000


async def test_web_search_emits_sources(monkeypatch):
    d = install()
    events = []
    monkeypatch.setattr(research, "emit", lambda t, **f: events.append((t, f)))
    monkeypatch.setattr(research, "current_thread_id", lambda: "th1")
    out = await research.web_search.ainvoke({"query": "skincare pov dry skin"})
    lines = out.splitlines()
    assert json.loads(lines[0])["mode"] == "mock" and len(lines) > 1
    assert len(events) == len(lines) - 1 and events[0][0] == "source.added"
    assert len(d.app.sources) == len(events) and d.app.sources[0][0] == "th1"


def test_web_provider_mode_and_platform():
    assert WebResearchProvider(Settings()).mode == "off"
    assert WebResearchProvider(Settings(firecrawl_api_key="k")).mode == "live"
    assert WebResearchProvider(Settings(internal_mode="edge", has_firecrawl=True)).mode == "live"
    assert platform_of("https://www.youtube.com/shorts/x") == "youtube"
    assert platform_of("https://youtu.be/x") == "youtube"
    assert platform_of("https://eviltiktok.com/x") is None


async def test_memory_roundtrip_and_empty_library():
    edge = FakeEdge()
    install(edge=edge)
    out = json.loads(await memory.remember_pattern.ainvoke({
        "title": "Label Warning!", "hook": "h", "hook_type": "negative_warning", "structure": "s",
        "why_it_works": "w", "source_urls": ["https://example.com/a"], "tags": ["t"]}))
    assert out["saved"] == "label-warning" and edge.upserts[0][0] == "default:patterns"
    res = json.loads(await memory.search_patterns.ainvoke({"query": "magnesium supplements"}))
    assert res["results"] == 0 and "SAMPLE" not in json.dumps(res)  # never sample patterns
    edge.matches = [{"id": "label-warning", "score": 0.9, "metadata": {"title": "Label Warning!"}}]
    assert json.loads(await memory.search_patterns.ainvoke({"query": "x"}))["label"] == "library"


async def test_post_metrics_deterministic():
    post = Post(id="p1", thread_id=None, account_id="a", asset_id=None, caption="c", ai_disclosure=True,
                status="published", mode="mock")
    install(app=FakeApp([post]))
    a = await analytics.get_post_metrics.ainvoke({})
    b = await analytics.get_post_metrics.ainvoke({"post_ids": ["p1"]})
    assert a == b
    row = json.loads(a.splitlines()[1])
    assert len(row["views_7d_cumulative"]) == 7 and row["views_7d_cumulative"] == sorted(row["views_7d_cumulative"])
    assert (await MockAnalytics().post_metrics([post]))[0]["views"] == row["views"]


def test_source_policy_blocks_scraping_routes():
    from ugecy.tools.source_policy import policy_error

    for bad in ["https://html.duckduckgo.com/html/?q=x", "https://r.jina.ai/https://x.com",
                "https://www.tikwm.com/api/?url=x", "https://www.tiktok.com/tag/vitaminc",
                "https://www.tiktok.com/@someone", "https://www.youtube.com/results?search_query=x",
                "https://p19-common-sign.tiktokcdn-us.com/a.jpg", "https://www.google.com/search?q=x"]:
        assert policy_error(bad), bad
    for ok in ["https://www.byrdie.com/viral-tiktok-vitamin-c-serum",
               "https://www.tiktok.com/@someone/video/123", "https://www.youtube.com/shorts/abc"]:
        assert policy_error(ok) is None, ok


def test_fetch_budget():
    from ugecy.tools import source_policy as sp

    sp._calls.clear()
    assert all(sp.take_budget("t1") is None for _ in range(sp.FETCH_BUDGET))
    assert sp.take_budget("t1") is not None
    assert sp.take_budget("t2") is None


def test_all_skills_have_valid_frontmatter():
    import pathlib

    import yaml

    for p in pathlib.Path(__file__).parents[1].joinpath("ugecy/skills").glob("*/SKILL.md"):
        meta = yaml.safe_load(p.read_text().split("---")[1])
        assert meta["name"] == p.parent.name and 0 < len(meta["description"]) <= 1024

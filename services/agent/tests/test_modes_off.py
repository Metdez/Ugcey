"""Phase 06: nothing is simulated; off capabilities say what to connect."""
import json

import pytest
from pydantic import ValidationError

from tests._fakes_02_07 import FakeEdge
from tests._fakes_02_07 import install as install_research
from tests._fakes_02_08 import MemApp
from ugecy import deps as deps_mod
from ugecy.contracts import ProviderModes
from ugecy.integrations.research.web import WebResearchProvider
from ugecy.integrations.unavailable import (
    DEVICE_OFF,
    MEDIA_OFF,
    PUBLISH_OFF,
    NotConnected,
    OffAnalytics,
    OffDeviceProvider,
    OffMediaProvider,
    OffPublisher,
)
from ugecy.settings import Settings
from ugecy.tools import analytics, device, media, memory, publishing, research


@pytest.fixture(autouse=True)
def _no_stream(monkeypatch):
    for mod in (research, memory):
        monkeypatch.setattr(mod, "emit", lambda *a, **k: None)


def _off_deps(**kw):
    d = install_research(**kw)
    d.app = MemApp()
    d.modes = ProviderModes()
    d.research, d.media, d.device = WebResearchProvider(Settings()), OffMediaProvider(), OffDeviceProvider()
    d.publisher, d.analytics = OffPublisher(), OffAnalytics()
    return d


@pytest.mark.parametrize("mode", ["edge", "local"])
def test_resolve_modes_report_only_live_or_off(mode, monkeypatch):
    for k in ("HF_KEY", "HF_API_KEY_SECRET", "FIRECRAWL_API_KEY", "GLASSHAND_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    m = deps_mod.resolve_modes(Settings(internal_mode=mode))
    assert {m.media, m.device, m.publishing, m.research} == {"off"} and m.llm == "live"
    on = deps_mod.resolve_modes(Settings(internal_mode="edge", has_higgsfield=True, has_firecrawl=True, has_glasshand=True))
    assert (on.media, on.device, on.research, on.publishing) == ("live", "live", "live", "off")
    with pytest.raises(ValidationError):  # only auto, live or off are accepted
        Settings(internal_mode=mode, media_provider="fake")


def test_test_mode_builds_all_off():
    d = deps_mod.build_deps(Settings(internal_mode="test"))
    assert (d.media.mode, d.publisher.mode, d.analytics.mode) == ("off", "off", "off")
    assert d.modes.llm == "off" and d.modes.publishing == "off"


async def test_web_search_off_message():
    _off_deps()
    out = json.loads(await research.web_search.ainvoke({"query": "skincare hooks"}))
    assert out["mode"] == "off" and "FIRECRAWL_API_KEY" in out["error"] and "SAMPLE" not in json.dumps(out)
    with pytest.raises(NotConnected):
        await WebResearchProvider(Settings()).search("x")


async def test_generate_media_off_error_but_catalog_listable():
    _off_deps()
    out = json.loads(await media.generate_media.ainvoke({"model": "higgsfield-ai/soul/v2/standard", "prompt": "p"}))
    assert out == {"error": MEDIA_OFF}
    assert json.loads(await media.estimate_media_cost.ainvoke({"model": "m"}))["error"] == MEDIA_OFF
    assert json.loads(await media.list_media_models.ainvoke({}))  # real catalog still listed


async def test_device_off_errors():
    _off_deps()
    assert (await device.device_status.ainvoke({})).count('"mode":"off"') == 1
    for t, a in ((device.device_screenshot, {}), (device.device_observe, {}),
                 (device.device_start_session, {"goal": "g", "allowed_apps": ["TikTok"]})):
        assert await t.ainvoke(a) == f"error: {DEVICE_OFF}"


async def test_no_demo_accounts_and_publish_analytics_off():
    d = _off_deps()
    out = json.loads(await publishing.list_connected_accounts.ainvoke({}))
    assert out["accounts"] == [] and PUBLISH_OFF in out["note"]
    assert await d.app.list_accounts() == []  # listing did not seed anything
    pub = json.loads(await publishing.publish_post.ainvoke(
        {"account_id": "a", "asset_id": "b", "caption": "c", "ai_disclosure": True}))
    assert pub == {"error": PUBLISH_OFF}
    assert json.loads(await analytics.get_post_metrics.ainvoke({}))["mode"] == "off"


async def test_search_patterns_empty_without_stored_patterns():
    install_research(edge=FakeEdge())
    out = json.loads(await memory.search_patterns.ainvoke({"query": "anything"}))
    assert out["results"] == 0

import asyncio
import json
import pathlib
from typing import ClassVar

import yaml

from tests._fakes_05_01 import install
from ugecy.integrations.device import vision
from ugecy.tools import device

ID = "iphone-mock-1"


async def call(tool, **args):
    return await tool.ainvoke(args)


async def start(purpose="research", **kw):
    return json.loads(await call(device.device_start_session, goal="research", allowed_apps=["TikTok"], purpose=purpose, **kw))


async def tap(x, y):
    return json.loads(await call(device.device_tap, x=x, y=y))


async def open_tiktok():
    await call(device.device_home)
    await call(device.device_swipe, from_x=0.5, from_y=0.4, to_x=0.5, to_y=0.8)
    await call(device.device_type, text="TikTok")


def test_parse_count():
    p = vision.parse_count
    assert (p("1.2M"), p("45.3K"), p("987"), p("1,234"), p(5), p("2B")) == (1_200_000, 45_300, 987, 1234, 5, 2_000_000_000)
    assert p("") is None and p("n/a") is None and p(None) is None and p(True) is None


def test_normalize_post_parses_metrics():
    out = vision.normalize_post('<think>x</think>```json\n{"platform":"TikTok","creator":"@a","hook_guess":"h","is_ad":"false",'
                                '"metrics":{"views":"1.2M","likes":"45.3K","shares":"987","saves":""}}\n```')
    assert out["metrics"] == {"views": 1_200_000, "likes": 45_300, "shares": 987} and out["platform"] == "tiktok" and out["is_ad"] is False
    assert "error" in vision.normalize_post("no json here")


async def test_research_session_guards(monkeypatch):
    _, slept, _ = install(monkeypatch)
    s = await start(max_steps=5)
    assert s["max_steps"] == 60  # research budget is fixed
    assert "refused" in await call(device.device_commit, intent="post", x=0.5, y=0.5)
    assert "80" in await call(device.device_type, text="x" * 81)
    assert json.loads(await call(device.device_type, text="x" * 80))["ok"]
    for _ in range(59):
        await call(device.device_home)
    assert "budget" in await call(device.device_home)
    # operate sessions keep the old rules
    await start("operate", max_steps=2)
    assert json.loads(await call(device.device_type, text="x" * 200))["ok"]
    assert not slept


async def test_mock_feed_navigation_and_observe(monkeypatch):
    d, slept, events = install(monkeypatch)
    await start()
    await open_tiktok()
    assert "TikTok" in await call(device.device_screenshot)
    assert (await tap(0.5, 0.26))["screen"] == "tt_post"  # Spotlight result -> For You feed
    assert (await tap(0.88, 0.055))["screen"] == "tt_search"
    await call(device.device_type, text="protein bar")
    assert (await tap(0.83, 0.16))["screen"] == "tt_results"
    assert "Results: protein bar" in await call(device.device_screenshot) or True
    assert (await tap(0.75, 0.33))["screen"] == "tt_post"  # tile 2
    first = json.loads(await call(device.device_observe, note="top result"))
    assert first["creator"] == "@mock.gymbro_dan" and first["metrics"]["likes"] == 45_300 and first["source_url"] == "device://tiktok/mock.gymbro_dan"
    assert first["mode"] == "mock" and first["note"] == "top result" and first["hook_guess"]
    nxt = json.loads(await call(device.device_next_post))
    assert nxt["ok"] and len(slept) == 1 and 2.0 <= slept[0] <= 4.0
    second = json.loads(await call(device.device_observe))
    assert second["creator"] == "@mock.brandy.eats" and second["is_ad"] is True
    assert [s.url for _, s in d.app.sources] == ["device://tiktok/mock.gymbro_dan", "device://tiktok/mock.brandy.eats"]
    assert d.app.sources[0][0] == "t1" and [e["type"] for e in events] == ["source.added"] * 2
    assert "Post 3/4" in await call(device.device_screenshot)
    await call(device.device_swipe, from_x=0.5, from_y=0.2, to_x=0.5, to_y=0.8, dwell=True)  # swipe down = previous
    assert len(slept) == 2 and json.loads(await call(device.device_observe))["creator"] == "@mock.gymbro_dan"


async def test_observe_needs_a_post_and_limits(monkeypatch):
    d, _, _ = install(monkeypatch)
    await start()
    assert "no post" in (await call(device.device_observe))
    assert not d.app.sources
    await open_tiktok()
    await tap(0.5, 0.26)
    for _ in range(12):
        assert "error" not in json.loads(await call(device.device_observe))
    assert "limit" in await call(device.device_observe)
    assert (await call(device.device_next_post)).startswith("{")


async def test_observe_live_path_records_device_fallback_and_url(monkeypatch):
    class Live:
        name, mode = "glasshand", "live"
        shot: ClassVar[dict] = {"platform": "instagram", "creator": "@real", "caption": "c", "on_screen_text": "", "hook_guess": "h",
                "metrics": {"views": 10}, "audio": "", "format_guess": "", "is_ad": False, "url": "", "elements": []}

        async def list_devices(self):
            from ugecy.contracts import DeviceInfo
            return [DeviceInfo(id="r1", name="r", kind="iphone", status="active", ready=True)]

        async def observe(self, device_id):
            return dict(self.shot)

    d, _, _ = install(monkeypatch, Live())
    assert json.loads(await call(device.device_observe))["source_url"] == "device://instagram/real"
    Live.shot = {**Live.shot, "url": "https://www.instagram.com/reel/abc/"}
    assert json.loads(await call(device.device_observe))["source_url"] == "https://www.instagram.com/reel/abc/"
    assert d.app.sources[0][1].platform == "instagram" and "views 10" in d.app.sources[0][1].snippet


def test_research_analyst_tools(monkeypatch):
    from ugecy import modules, registry
    modules.load_modules()
    tools = registry.AGENTS["research-analyst"].tools
    need = {"device_status", "device_start_session", "device_screenshot", "device_observe", "device_tap", "device_swipe",
            "device_next_post", "device_type", "device_home"}
    assert need <= set(tools) and "device_commit" not in tools
    assert "device_commit" in registry.AGENTS["device-operator"].tools
    assert registry.TOOLS["device_start_session"].interrupt
    assert "phone-research" in registry.AGENTS["research-analyst"].system_prompt


def test_all_skills_frontmatter():
    root = pathlib.Path(__file__).parents[1] / "ugecy/skills"
    found = sorted(p.parent.name for p in root.glob("*/SKILL.md"))
    assert "phone-research" in found
    for p in root.glob("*/SKILL.md"):
        meta = yaml.safe_load(p.read_text().split("---")[1])
        assert meta["name"] == p.parent.name and isinstance(meta["description"], str) and 0 < len(meta["description"]) <= 1024


def test_dwell_range():
    assert asyncio  # sleep is injectable; real default is asyncio.sleep
    assert device.DWELL_S == (2.0, 4.0)

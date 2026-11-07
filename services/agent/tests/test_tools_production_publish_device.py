import json

from tests._doubles.device import MockDeviceProvider
from tests._fakes_02_08 import install
from ugecy.contracts import Asset, ConnectedAccount
from ugecy.tools import device, publishing


def _asset(status="completed", provider="mock-media"):
    return Asset(id="a1", thread_id=None, kind="video", status=status, provider=provider, model="m", prompt="p", mode="mock", url="data:x")


async def _setup(**kw):
    d = install(**kw)
    await d.app.upsert_asset(_asset(**{k: v for k, v in kw.items() if k in ("status",)}))
    await d.app.upsert_account(ConnectedAccount(id="acct_tiktok", platform="tiktok", handle="@test", mode="mock"))
    accts = json.loads(await publishing.list_connected_accounts.ainvoke({}))
    return d, accts[0]["id"]


async def _pub(acct, **over):
    args = {"account_id": acct, "asset_id": "a1", "caption": "hi", "ai_disclosure": True} | over
    return json.loads(await publishing.publish_post.ainvoke(args))


async def test_publish_validations():
    d, acct = await _setup()
    assert "ai_disclosure" in (await _pub(acct, ai_disclosure=False))["error"]
    assert "unknown account" in (await _pub("nope"))["error"]
    assert "unknown asset" in (await _pub(acct, asset_id="zz"))["error"]
    assert "too long" in (await _pub(acct, caption="x" * 2201))["error"]
    assert "ISO" in (await _pub(acct, publish_at="tomorrow-ish"))["error"]
    await d.app.upsert_asset(_asset(status="queued"))
    assert "not ready" in (await _pub(acct))["error"]
    assert not d.app.posts and all(a.status == "rejected" for a in d.app.audit if a.action == "publish")


async def test_publish_now_and_job_idempotent():
    d, acct = await _setup()
    out = await _pub(acct)
    assert out["status"] == "published" and "example.com/mock/tiktok/" in out["external_url"]
    again = await publishing.run_publish_job(out["post_id"])
    assert again["noop"] and len([a for a in d.app.audit if a.action == "publish" and a.status == "ok"]) == 1
    assert json.loads(await publishing.get_post_status.ainvoke({"post_id": out["post_id"]}))["status"] == "published"


async def test_scheduled_edge_vs_local():
    d, acct = await _setup(internal_mode="edge")
    out = await _pub(acct, publish_at="2999-01-01T00:00:00Z")
    assert out["status"] == "scheduled" and d.edge.scheduled[0][0] == out["post_id"]
    d2, acct2 = await _setup()
    out2 = await _pub(acct2, publish_at="2999-01-01T00:00:00Z")
    assert out2["status"] == "published" and "local mode" in out2["note"] and not d2.edge.scheduled


async def test_mock_device_hit_testing():
    p = MockDeviceProvider()
    assert (await p.send("iphone-mock-1", {"type": "tap", "x": 0.2, "y": 0.15}, idempotency_key="1"))["screen"] == "photos"
    assert "video_001.mp4" in await p.describe("iphone-mock-1")
    miss = await p.send("iphone-mock-1", {"type": "tap", "x": 0.9, "y": 0.9}, idempotency_key="2")
    assert miss["ok"] and miss["screen"] == "photos"
    assert (await p.send("iphone-mock-1", {"type": "tap", "x": 2, "y": 0}, idempotency_key="3"))["error"] == "invalid_coordinates"
    assert (await p.send("iphone-mock-1", {"type": "type", "text": "é"}, idempotency_key="4"))["error"] == "invalid_text"
    r = await p.send("iphone-mock-1", {"type": "tap", "x": 0.2, "y": 0.15}, idempotency_key="1")  # replayed key: no double action
    assert r["screen"] == "photos"
    assert (await p.screenshot("iphone-mock-1"))[:2] == b"\xff\xd8"
    await p.send("iphone-mock-1", {"type": "home"}, idempotency_key="5")
    assert "Home" in await p.describe("iphone-mock-1")


async def test_device_session_guard_and_commit_flow():
    install()
    device.reset_state()
    assert device_err(await device.device_tap.ainvoke({"x": 0.2, "y": 0.15}))
    await device.device_start_session.ainvoke({"goal": "post video", "allowed_apps": ["TikTok"], "max_steps": 3})
    await device.device_tap.ainvoke({"x": 0.58, "y": 0.16})  # TikTok -> upload
    await device.device_tap.ainvoke({"x": 0.77, "y": 0.91})  # Next -> caption
    assert device_err(await device.device_commit.ainvoke({"intent": "bogus", "x": 0.7, "y": 0.9}))
    out = json.loads(await device.device_commit.ainvoke({"intent": "post", "x": 0.77, "y": 0.91}))
    assert out["screen"] == "posted" and out["steps_left"] == 0
    assert "budget" in await device.device_home.ainvoke({})
    snap = await device.device_status_snapshot()
    assert snap.session.steps_used == 3 and snap.mode == "mock" and snap.devices[0].id == "iphone-mock-1"
    d = device.get_deps()
    assert [a.tool for a in d.app.audit if a.tool != "device_start_session"] == ["device_tap", "device_tap", "device_commit"]


def device_err(s: str) -> bool:
    return s.startswith("error")

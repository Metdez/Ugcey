import asyncio
import importlib
import json
from importlib import resources

import httpx
import pytest

from tests._doubles.media import MockMediaProvider
from tests._fakes_02_08 import install
from ugecy import registry
from ugecy.integrations.media.higgsfield import HiggsfieldProvider
from ugecy.settings import Settings
from ugecy.tools import media


def test_catalog_is_package_data():
    text = resources.files("ugecy.integrations.media").joinpath("catalog.yaml").read_text()
    assert "higgsfield-ai/soul/v2/standard" in text
    assert {m["kind"] for m in MockMediaProvider().models()} == {"image", "video"}
    assert all(m["defaults"].get("aspect_ratio", "9:16") == "9:16" for m in MockMediaProvider().models("image"))


async def test_mock_lifecycle_and_faults():
    now = [0.0]
    p = MockMediaProvider(clock=lambda: now[0])
    ok = await p.submit("bytedance/seedance-2.5/text-to-video", {"prompt": "hi"}, idempotency_key="k1")
    again = await p.submit("bytedance/seedance-2.5/text-to-video", {"prompt": "hi"}, idempotency_key="k1")
    assert again.job_id == ok.job_id and ok.status == "queued"
    bad = await p.submit("higgsfield-ai/soul/v2/standard", {"prompt": "x [mock:fail]"}, idempotency_key="k2")
    nsfw = await p.submit("higgsfield-ai/soul/v2/standard", {"prompt": "x [mock:nsfw]"}, idempotency_key="k3")
    now[0] = 3
    assert (await p.get(ok.job_id)).status == "in_progress"
    now[0] = 7
    done = await p.get(ok.job_id)
    assert done.status == "completed" and done.outputs[0]["kind"] == "video" and done.outputs[0]["url"].startswith("data:image/svg")
    assert (await p.get(bad.job_id)).status == "failed" and (await p.get(nsfw.job_id)).status == "nsfw"


def _hf(handler, mode="local"):
    s = Settings(internal_mode=mode, hf_key="id:secret")
    return HiggsfieldProvider(s, transport=httpx.MockTransport(handler))


async def test_higgsfield_submit_idempotency_retry_after_and_outputs(monkeypatch):
    sleeps, calls = [], []
    monkeypatch.setattr("ugecy.integrations.media.higgsfield.asyncio.sleep", lambda s: _rec(sleeps, s))

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        if req.url.path == "/bytedance/seedance-2.5/text-to-video":
            if len(calls) == 1:
                return httpx.Response(429, headers={"Retry-After": "3"}, json={"detail": {"message": "queue full"}})
            return httpx.Response(200, json={"status": "queued", "request_id": "r1"})
        if req.url.path == "/requests/r1/status":
            return httpx.Response(200, json={"status": "completed", "images": [{"url": "https://x/a.png"}], "video": {"url": "https://x/v.mp4"}})
        if req.url.path.startswith("/estimate/"):
            return httpx.Response(200, json={"usd": "0.094"})
        return httpx.Response(404, json={"detail": "nope"})

    p = _hf(handler)
    job = await p.submit("bytedance/seedance-2.5/text-to-video", {"prompt": "p"}, idempotency_key="abc")
    assert job.job_id == "r1" and sleeps == [3.0]
    assert [r.headers["Idempotency-Key"] for r in calls] == ["abc", "abc"]
    assert calls[0].headers["Authorization"] == "Key id:secret"
    got = await p.get("r1")
    assert got.outputs == [{"url": "https://x/a.png", "kind": "image"}, {"url": "https://x/v.mp4", "kind": "video"}]
    assert await p.estimate("m/x", {}) == 0.094
    edge = _hf(handler, mode="edge")
    assert str(edge._client.base_url).startswith("http://higgsfield.internal") and "Authorization" not in edge._client.headers


async def _rec(lst, s):
    lst.append(s)


async def test_generate_media_flow_and_poller(monkeypatch):
    d = install()
    monkeypatch.setitem(media.POLL, "first", 0.01)
    out = json.loads(await media.generate_media.ainvoke({"model": "higgsfield-ai/soul/v2/standard", "prompt": "a creator"}))
    assert out["status"] == "queued" and out["mode"] == "mock"
    await asyncio.gather(*media._tasks)
    asset = d.app.assets[out["asset_id"]]
    assert asset.status == "completed" and asset.url.startswith("data:") and asset.estimated_usd
    assert [a.action for a in d.app.audit] == ["media_job", "media_job"]
    assert json.loads(await media.check_media_job.ainvoke({"asset_id": asset.id}))["status"] == "completed"
    assert await media.estimate_for_approval({"model": "higgsfield-ai/soul/v2/standard", "prompt": "x"}) > 0
    assert await media.estimate_for_approval({}) is None
    assert "error" in json.loads(await media.generate_media.ainvoke({"model": "nope", "prompt": "x"}))


async def test_failed_job_marks_asset_failed(monkeypatch):
    d = install()
    monkeypatch.setitem(media.POLL, "first", 0.01)
    out = json.loads(await media.generate_media.ainvoke({"model": "higgsfield-ai/soul/v2/standard", "prompt": "[mock:fail]"}))
    await asyncio.gather(*media._tasks)
    assert d.app.assets[out["asset_id"]].status == "failed" and d.app.audit[-1].status == "error"


def test_tools_registered_with_expected_interrupts(monkeypatch):
    monkeypatch.setattr(registry, "TOOLS", {})
    for m in ("media", "publishing", "device"):
        importlib.reload(importlib.import_module(f"ugecy.tools.{m}"))
    T = registry.TOOLS
    assert T["generate_media"].interrupt == registry.APPROVE_EDIT_REJECT and T["generate_media"].side_effect
    assert T["publish_post"].interrupt == registry.APPROVE_EDIT_REJECT and T["publish_post"].side_effect
    assert T["device_start_session"].interrupt == registry.APPROVE_REJECT
    assert T["device_commit"].interrupt == registry.APPROVE_REJECT and T["device_commit"].side_effect
    for n in ("list_media_models", "estimate_media_cost", "check_media_job", "list_connected_accounts", "get_post_status",
              "device_status", "device_screenshot", "device_tap", "device_swipe", "device_type", "device_home"):
        assert n in T and not T[n].interrupt
    assert {s.domain for s in T.values()} == {"media", "publishing", "device"}
    pytest.importorskip("ugecy.tools.media")

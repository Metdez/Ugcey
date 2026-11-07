"""Plan 05-02: chaining image assets into video args, approval estimates, durable polling."""
import asyncio
import json

import httpx

from tests._fakes_02_08 import FakeEdge, MemApp, install
from ugecy.contracts import Asset
from ugecy.integrations.media.higgsfield import HiggsfieldProvider
from ugecy.settings import Settings
from ugecy.tools import media

I2V = "bytedance/seedance-2.5/image-to-video"


class Recorder:
    """httpx handler: records submits, serves estimates, and reports a job as in_progress then completed."""

    def __init__(self):
        self.submits, self.polls = [], 0

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if req.url.path.startswith("/estimate/"):
            return httpx.Response(200, json={"usd": "0.5"})
        if req.method == "POST":
            self.submits.append((req.url.path, json.loads(req.content)))
            return httpx.Response(200, json={"status": "queued", "request_id": f"r{len(self.submits)}"})
        self.polls += 1
        if self.polls == 1:
            return httpx.Response(200, json={"status": "in_progress", "request_id": "r1"})
        return httpx.Response(200, json={"status": "completed", "request_id": "r1", "expires_at": "2026-11-14T00:00:00Z",
                                         "video": {"url": "https://cdn.example/v.mp4"}})


def _live(rec):
    p = HiggsfieldProvider(Settings(internal_mode="local", hf_key="id:secret"), transport=httpx.MockTransport(rec))
    d = install(media=p)
    return d


def _still(d, url="https://cdn.example/still.png", status="completed"):
    a = Asset(id="asset_still", thread_id=None, kind="image", status=status, provider="higgsfield", model="m", prompt="p",
              url=url, mode="live")
    d.app.assets[a.id] = a


async def test_image_asset_chains_into_image_url_and_estimate(monkeypatch):
    monkeypatch.setitem(media.POLL, "first", 0.01)
    rec = Recorder()
    d = _live(rec)
    _still(d)
    out = json.loads(await media.generate_media.ainvoke({"model": I2V, "prompt": "she waves", "image_asset_id": "asset_still"}))
    assert out["estimated_usd"] == 0.5
    path, body = rec.submits[0]
    assert path == "/" + I2V and body == {"duration": 5, "resolution": "720p", "generate_audio": True,
                                           "image_url": "https://cdn.example/still.png", "prompt": "she waves"}
    await asyncio.gather(*media._tasks)
    # approval card price works for the chained args, and even when the still is not resolvable
    assert await media.estimate_for_approval({"model": I2V, "prompt": "x", "image_asset_id": "asset_still"}) == 0.5
    assert await media.estimate_for_approval({"model": I2V, "prompt": "x", "image_asset_id": "gone"}) == 0.5


async def test_reference_assets_and_chain_errors():
    rec = Recorder()
    d = _live(rec)
    _still(d)
    r = json.loads(await media.generate_media.ainvoke({"model": "bytedance/seedance-2.5/reference-to-video", "prompt": "p",
                                                       "reference_asset_ids": ["asset_still"]}))
    assert "error" not in r and rec.submits[0][1]["image_urls"] == ["https://cdn.example/still.png"]
    for args, needle in [({"model": I2V, "prompt": "p"}, "needs image_url"),
                         ({"model": I2V, "prompt": "p", "image_asset_id": "nope"}, "unknown asset")]:
        assert needle in json.loads(await media.generate_media.ainvoke(args))["error"]
    _still(d, status="in_progress")
    assert "not completed" in json.loads(await media.generate_media.ainvoke({"model": I2V, "prompt": "p", "image_asset_id": "asset_still"}))["error"]
    assert len(rec.submits) == 1  # none of the rejected calls spent money


async def test_submit_failure_is_a_tool_error_not_a_stack_trace():
    d = _live(lambda req: httpx.Response(403, json={"detail": "no balance"}) if req.method == "POST" and "estimate" not in req.url.path
               else httpx.Response(200, json={"usd": "0.5"}))
    out = json.loads(await media.generate_media.ainvoke({"model": "higgsfield-ai/soul/v2/standard", "prompt": "p"}))
    assert "insufficient Higgsfield balance" in out["error"] and "Traceback" not in out["error"]
    assert d.app.audit[-1].status == "error"


async def test_resume_media_jobs_completes_orphaned_asset(monkeypatch):
    monkeypatch.setitem(media.POLL, "first", 0.01)
    rec = Recorder()
    d = _live(rec)
    app: MemApp = d.app
    app.list_assets = lambda thread_id=None: _aval(list(app.assets.values()))
    edge: FakeEdge = d.edge
    for aid, status, job in (("a_run", "in_progress", "r1"), ("a_done", "completed", "r9"), ("a_nojob", "queued", None)):
        app.assets[aid] = Asset(id=aid, thread_id="t1", kind="video", status=status, provider="higgsfield", model=I2V, prompt="p",
                                job_id=job, mode="live", url="https://x/y.mp4" if status == "completed" else None)
    assert await media.resume_media_jobs() == 1
    assert await media.resume_media_jobs() == 0  # already being polled
    await asyncio.gather(*media._tasks)
    a = app.assets["a_run"]
    assert a.status == "completed" and a.url == "https://cdn.example/v.mp4"
    assert edge.ingested == [("a_run", "https://cdn.example/v.mp4", "video")]
    assert app.assets["a_done"].status == "completed" and rec.polls == 2
    ok = [e for e in app.audit if e.status == "ok"][-1]
    assert "expires_at=2026-11-14T00:00:00Z" in ok.detail and "7 days" in ok.detail


async def _aval(v):
    return v



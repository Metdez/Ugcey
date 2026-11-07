"""Plan 05-02: Higgsfield adapter against the documented API shapes (httpx.MockTransport, no network)."""
import json

import httpx
import pytest

from ugecy.integrations.media.catalog import catalog_models
from ugecy.integrations.media.higgsfield import HiggsfieldError, HiggsfieldProvider, parse_estimate
from ugecy.settings import Settings

SEEDANCE_DESC = (
    "For 16:9 video without video input, your request costs roughly $0.2056 per second of generated video at 480p, "
    "$0.4622 at 720p, and $1.1372 at 1080p. Each 1,000 video tokens costs $0.0214 at 480p or 720p and $0.0234 at 1080p.")
WAN_DESC = "Priced per generated second by resolution: 480p $0.05, 720p $0.10, or 1080p $0.20. Rates shown are before any applicable customer discount."


def _hf(handler):
    return HiggsfieldProvider(Settings(internal_mode="local", hf_key="id:secret"), transport=httpx.MockTransport(handler))


def test_catalog_loads_and_every_model_has_ugc_defaults():
    ms = catalog_models()
    ids = {m["endpoint_id"] for m in ms}
    assert {"higgsfield-ai/soul/v2/standard", "marketing-studio/image", "bytedance/seedance-2.5/text-to-video",
            "bytedance/seedance-2.5/image-to-video", "bytedance/seedance-2.5/reference-to-video",
            "kling-video/v3.0/std/image-to-video"} <= ids
    for m in ms:
        assert m["defaults"] and m["cost_hint"] and m["kind"] in ("image", "video") and m["label"], m["endpoint_id"]
        if m["kind"] == "video" and "duration" in m["defaults"]:
            assert m["defaults"]["duration"] == 5
    for m in ms:  # i2v models take the ratio from the still; everything else must default to vertical
        if "aspect_ratio" in m["defaults"]:
            assert m["defaults"]["aspect_ratio"] == "9:16"
    assert next(m for m in ms if m["endpoint_id"].endswith("seedance-2.5/image-to-video"))["requires"] == ["image_url"]


def test_parse_estimate_fixed_and_per_second():
    assert parse_estimate({"type": "estimate", "credits": "0.050", "usd": "0.004", "discount": None}, {}) == 0.004
    # the live bug: seedance answers {type: description, pricing_description} with no usd
    body = {"type": "description", "pricing_description": SEEDANCE_DESC}
    assert parse_estimate(body, {"resolution": "720p", "duration": 5}) == pytest.approx(2.311)
    assert parse_estimate(body, {"resolution": "480p", "duration": 4}) == pytest.approx(0.8224)
    assert parse_estimate({"pricing_description": WAN_DESC}, {"resolution": "480p", "duration": 5}) == pytest.approx(0.25)
    assert parse_estimate({"pricing_description": "Per 1M tokens: text input $5"}, {}) is None
    assert parse_estimate({"pricing_description": "Price estimation is unavailable for this model."}, {}) is None


async def test_estimate_seedance_via_http_and_swallowed_errors():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/estimate/bytedance/seedance-2.5/text-to-video":
            assert json.loads(req.content) == {"prompt": "t", "aspect_ratio": "9:16", "duration": 5, "resolution": "720p"}
            return httpx.Response(200, json={"type": "description", "pricing_description": SEEDANCE_DESC})
        return httpx.Response(403, json={"detail": "no"})

    p = _hf(handler)
    args = {"prompt": "t", "aspect_ratio": "9:16", "duration": 5, "resolution": "720p"}
    assert await p.estimate("bytedance/seedance-2.5/text-to-video", args) == pytest.approx(2.311)
    assert await p.estimate("other/model", {}) is None


@pytest.mark.parametrize("status,headers,body,needle", [
    (403, {}, {"detail": "Not enough credits"}, "insufficient Higgsfield balance"),
    (422, {}, {"detail": [{"loc": ["body", "duration"], "msg": "ensure this value is <= 30"}]}, "duration: ensure this value"),
    (429, {"Retry-After": "7"}, {"detail": {"code": "account_queue_full", "message": "full", "retry_after_seconds": 7}}, "account_queue_full"),
])
async def test_error_mapping_reads_as_tool_error(monkeypatch, status, headers, body, needle):
    async def nosleep(_s):
        return None

    monkeypatch.setattr("ugecy.integrations.media.higgsfield.asyncio.sleep", nosleep)
    p = _hf(lambda req: httpx.Response(status, headers={**headers, "X-Correlation-ID": "c1"}, json=body))
    with pytest.raises(HiggsfieldError) as ei:
        await p.submit("higgsfield-ai/soul/v2/standard", {"prompt": "x"}, idempotency_key="k")
    msg = str(ei.value)
    assert needle in msg and "c1" in msg and ei.value.status == status
    if status == 429:
        assert "7 s" in msg


async def test_status_shapes_images_video_audio_nsfw():
    bodies = {
        "img": {"status": "completed", "request_id": "img", "expires_at": "2026-11-14T00:00:00Z", "images": [{"url": "https://c/1.jpg"}, {"url": "https://c/2.jpg"}]},
        "vid": {"status": "completed", "request_id": "vid", "video": {"url": "https://c/v.mp4"}},
        "aud": {"status": "completed", "request_id": "aud", "audio": {"url": "https://c/a.mp3"}, "audios": [{"url": "https://c/a.mp3"}]},
        "bad": {"status": "nsfw", "request_id": "bad"},
        "run": {"status": "in_progress", "request_id": "run"},
    }
    p = _hf(lambda req: httpx.Response(200, json=bodies[req.url.path.split("/")[2]]))
    img = await p.get("img")
    assert [o["url"] for o in img.outputs] == ["https://c/1.jpg", "https://c/2.jpg"] and img.outputs[0]["expires_at"] == "2026-11-14T00:00:00Z"
    assert (await p.get("vid")).outputs[0] == {"url": "https://c/v.mp4", "kind": "video"}
    assert [o["kind"] for o in (await p.get("aud")).outputs] == ["audio"]
    bad = await p.get("bad")
    assert bad.status == "nsfw" and bad.error and not bad.outputs
    assert (await p.get("run")).status == "in_progress"


@pytest.mark.parametrize("model,args", [(m["endpoint_id"], {}) for m in catalog_models()])
async def test_every_catalog_model_args_reach_the_wire(model, args):
    """Defaults + prompt are what the estimate and submit POST for each model."""
    from tests._fakes_02_08 import install
    from ugecy.tools.media import _merged_args

    seen = []
    p = _hf(lambda req: (seen.append(json.loads(req.content)), httpx.Response(200, json={"usd": "0.1"}))[1])
    install(media=p)
    full = _merged_args(model, "a prompt", args)
    assert await p.estimate(model, full) == 0.1
    spec = next(m for m in catalog_models() if m["endpoint_id"] == model)
    assert seen[0] == {**spec["defaults"], "prompt": "a prompt"}

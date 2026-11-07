import io
import json

import httpx
import pytest
from PIL import Image

from tests._fakes_04_02 import FakeVision, gateway, jpeg, vision_json
from ugecy.integrations.device import vision
from ugecy.integrations.device.glasshand import GlasshandProvider, map_action
from ugecy.settings import Settings

EDGE = Settings(internal_mode="edge")


def prov(handler, **kw):
    return GlasshandProvider(EDGE, transport=httpx.MockTransport(handler), **kw)


def test_crop_math_and_scaling():
    img = Image.new("RGB", (100, 200))
    geo = {"width": 100, "height": 200, "viewport": {"x": 10, "y": 20, "width": 50, "height": 60}}
    assert vision.crop_viewport(img, geo).size == (50, 60)
    assert vision.crop_viewport(Image.new("RGB", (200, 400)), geo).size == (100, 120)  # image 2x geometry
    over = {"width": 100, "height": 200, "viewport": {"x": 90, "y": 190, "width": 50, "height": 60}}
    assert vision.crop_viewport(img, over).size == (10, 10)  # clamped
    tall = vision.to_jpeg(Image.new("RGB", (500, 2000)), max_h=900)
    assert Image.open(io.BytesIO(tall)).size == (225, 900)


def test_input_mapping():
    assert map_action({"type": "tap", "x": 0.2, "y": 0.9}) == {"type": "click", "x": 0.2, "y": 0.9}
    assert map_action({"type": "swipe", "from_x": 0.5, "from_y": 0.8, "to_x": 0.5, "to_y": 0.2}) == {
        "type": "drag", "fromX": 0.5, "fromY": 0.8, "toX": 0.5, "toY": 0.2, "durationMs": 400}
    assert map_action({"type": "type", "text": "hi\n"}) == {"type": "text", "text": "hi\n"}
    assert map_action({"type": "home"}) == {"type": "home"}
    for bad, code in [({"type": "tap", "x": 1.5, "y": 0}, "invalid_coordinates"), ({"type": "type", "text": "é"}, "invalid_text"),
                      ({"type": "type", "text": "a" * 513}, "invalid_text"), ({"type": "zap"}, "unsupported_action")]:
        with pytest.raises(ValueError, match=code):
            map_action(bad)


async def test_list_screenshot_and_geometry_cached():
    seen = []
    p = prov(gateway(seen=seen))
    devs = await p.list_devices()
    assert {d.id: d.ready for d in devs} == {"r1": True, "r2": False, "r3": True}
    assert Image.open(io.BytesIO(await p.screenshot("r1"))).size == (50, 60)
    await p.screenshot("r1")
    assert sum(r.url.path.endswith("/connection") for r in seen) == 1


async def test_send_receipt_error_code_and_key():
    seen = []
    body = {"v": 1, "type": "result", "requestId": "q", "ok": False, "error": {"code": "control_taken"}}
    p = prov(gateway(seen=seen, input_body=body))
    r = await p.send("r1", {"type": "tap", "x": 0.5, "y": 0.5}, idempotency_key="k")
    assert r["error_code"] == "control_taken" and r["error"] == "control_taken" and not r["ok"] and r["request_id"] == "q"
    assert seen[-1].headers["Idempotency-Key"] == "k" and json.loads(seen[-1].content)["type"] == "click"
    assert seen[-1].url.path == "/v1/rentals/r1/input"
    ok = await prov(gateway()).send("r1", {"type": "home"}, idempotency_key="k2")
    assert ok["ok"] and ok["error_code"] is None
    bad = await p.send("r1", {"type": "tap", "x": 9, "y": 0}, idempotency_key="k3")
    assert bad["error_code"] == "invalid_coordinates" and len(seen) == 1  # nothing sent


async def test_http_error_becomes_code():
    def h(req):
        return httpx.Response(409, json={"error": {"code": "control_busy"}})
    r = await prov(h).send("r1", {"type": "home"}, idempotency_key="k")
    assert r["error_code"] == "control_busy"
    r = await prov(lambda req: httpx.Response(502, text="bad gateway")).send("r1", {"type": "home"}, idempotency_key="k")
    assert r["error_code"] == "http_502"


@pytest.mark.parametrize("raw", [
    vision_json(),
    "Here you go:\n```json\n" + vision_json() + "\n```\nHope it helps!",
    "<think>hmm {not json}</think>" + vision_json(),
    "Sure. {oops} then " + vision_json(),
])
def test_extract_json_messy(raw):
    out = json.loads(vision.normalize(raw))
    assert out["app"] == "Home" and out["elements"] == [{"label": "Safari", "kind": "icon", "x": 0.3, "y": 0.8}]


def test_normalize_clamps_and_drops():
    raw = json.dumps({"elements": [{"label": "a", "kind": "weird", "x": 1.7, "y": -1}, {"label": "b", "x": "n/a", "y": 0.1}, "junk"]})
    out = json.loads(vision.normalize(raw))
    assert out["elements"] == [{"label": "a", "kind": "text", "x": 1.0, "y": 0.0}]
    assert json.loads(vision.normalize("no json here"))["elements"] == []


async def test_describe_sends_cropped_downscaled_data_uri():
    model = FakeVision("```json\n" + vision_json() + "\n```")

    def h(req):
        if req.url.path.endswith("/screenshot"):
            return httpx.Response(200, content=jpeg((1000, 3000)))
        return gateway()(req)

    geo_big = {"width": 1000, "height": 3000, "viewport": {"x": 0, "y": 0, "width": 1000, "height": 2000}}
    p = prov(h, vision_model=model)
    p._geometry["r1"] = geo_big
    out = json.loads(await p.describe("r1"))
    assert out["screen"] == "Home Screen"
    content = model.calls[0][0]["content"]
    assert "AssistiveTouch" in content[0]["text"] and "Spotlight" in content[0]["text"]
    url = content[1]["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")
    import base64
    assert Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).size == (450, 900)

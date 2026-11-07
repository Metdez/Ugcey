import io

import httpx
from PIL import Image

from ugecy.integrations.device.glasshand import GlasshandProvider
from ugecy.settings import Settings


async def test_glasshand_list_screenshot_send():
    seen = []
    buf = io.BytesIO()
    Image.new("RGB", (100, 200), "red").save(buf, "JPEG")

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        p = req.url.path
        if p == "/rentals":
            return httpx.Response(200, json={"items": [
                {"id": "r1", "kind": "iphone", "name": "SE", "status": "active", "deviceReady": True},
                {"id": "r2", "kind": "iphone", "name": "x", "status": "provisioning", "deviceReady": False}]})
        if p.endswith("/connection"):
            return httpx.Response(200, json={"geometry": {"width": 100, "height": 200, "viewport": {"x": 10, "y": 20, "width": 50, "height": 60}}})
        if p.endswith("/screenshot"):
            return httpx.Response(200, content=buf.getvalue())
        return httpx.Response(200, json={"v": 1, "type": "result", "requestId": "q", "ok": False, "error": {"code": "control_taken"}})

    p = GlasshandProvider(Settings(internal_mode="edge"), transport=httpx.MockTransport(handler))
    assert [d.id for d in await p.list_devices()] == ["r1"]
    assert Image.open(io.BytesIO(await p.screenshot("r1"))).size == (50, 60)
    r = await p.send("r1", {"type": "tap", "x": 0.5, "y": 0.5}, idempotency_key="k")
    assert r["error"] == "control_taken" and not r["ok"]
    assert seen[-1].headers["Idempotency-Key"] == "k" and b'"click"' in seen[-1].content

import io
import json
from types import SimpleNamespace

import httpx
from PIL import Image


def jpeg(size=(100, 200), color="red") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    return buf.getvalue()


class FakeVision:
    """Fake chat model: records messages, returns canned content."""

    def __init__(self, content="{}"):
        self.content, self.calls = content, []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        return SimpleNamespace(content=self.content)


GEO = {"width": 100, "height": 200, "viewport": {"x": 10, "y": 20, "width": 50, "height": 60}}


def gateway(status=None, seen=None, input_body=None, big=False):
    """MockTransport handler for glasshand.internal. status=None -> status endpoint unreachable."""
    def handler(req: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(req)
        p = req.url.path
        if p == "/_ugecy/status":
            if status is None:
                raise httpx.ConnectError("down")
            return httpx.Response(200, json=status)
        if p == "/v1/rentals":
            return httpx.Response(200, json={"items": [
                {"id": "r1", "kind": "iphone", "name": "SE", "status": "active", "deviceReady": True},
                {"id": "r2", "kind": "iphone", "name": "x", "status": "provisioning", "deviceReady": False},
                {"id": "r3", "kind": "iphone", "name": "y", "status": "grace", "deviceReady": True}]})
        if p.endswith("/connection"):
            return httpx.Response(200, json={"geometry": GEO})
        if p.endswith("/screenshot"):
            return httpx.Response(200, content=jpeg((100, 200)))
        return httpx.Response(200, json=input_body or {"v": 1, "type": "result", "requestId": "q", "ok": True})
    return handler


def vision_json(**kw) -> str:
    return json.dumps({"app": "Home", "screen": "Home Screen", "elements": [{"label": "Safari", "kind": "icon", "x": 0.3, "y": 0.8}], **kw})

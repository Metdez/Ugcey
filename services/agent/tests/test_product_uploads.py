"""Product photo uploads (API + Higgsfield presigned upload) and end-frame chaining for image-to-video."""
import base64
import json

import httpx
import pytest
from _fakes_02_04 import make_agent, make_client
from langchain_core.messages import AIMessage

from tests._doubles.media import FakeMediaProvider
from tests._fakes_02_08 import install
from ugecy.api.uploads import MAX_BYTES
from ugecy.contracts import Asset, ThreadSummary
from ugecy.integrations.media.higgsfield import HiggsfieldProvider
from ugecy.settings import Settings
from ugecy.tools import media

AGENT = make_agent([AIMessage(content="ok", id="m")])
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()


def _client():
    client, deps = make_client(AGENT)
    deps.media = FakeMediaProvider(t_progress=0.0, t_done=0.0)
    return client, deps


async def test_upload_creates_completed_image_asset_on_the_thread():
    client, deps = _client()
    await deps.app.upsert_thread(ThreadSummary(id="t1", title="x"))
    async with client:
        r = await client.post("/api/threads/t1/uploads", json={"filename": "lipstick.png", "content_type": "image/png",
                                                               "data_base64": PNG})
        assert r.status_code == 200, r.text
        a = r.json()
        assert (a["kind"], a["status"], a["provider"], a["model"], a["prompt"], a["thread_id"]) == (
            "image", "completed", "upload", "upload", "lipstick.png", "t1")
        assert a["url"].startswith("data:image/png;base64,")
        listed = (await client.get("/api/assets", params={"thread_id": "t1"})).json()
        assert [x["id"] for x in listed] == [a["id"]]


@pytest.mark.parametrize("body,status,code", [
    ({"filename": "a.gif", "content_type": "image/gif", "data_base64": PNG}, 415, "unsupported_type"),
    ({"filename": "a.pdf", "content_type": "application/pdf", "data_base64": PNG}, 415, "unsupported_type"),
    ({"filename": "a.png", "content_type": "image/png", "data_base64": "!!notbase64"}, 422, "validation_error"),
    ({"filename": "big.png", "content_type": "image/png",
      "data_base64": base64.b64encode(b"x" * (MAX_BYTES + 1)).decode()}, 413, "too_large"),
])
async def test_upload_rejects_bad_type_size_and_encoding(body, status, code):
    client, deps = _client()
    await deps.app.upsert_thread(ThreadSummary(id="t1", title="x"))
    async with client:
        r = await client.post("/api/threads/t1/uploads", json=body)
        assert r.status_code == status and r.json()["error"]["code"] == code


async def test_upload_needs_an_existing_thread():
    client, _ = _client()
    async with client:
        r = await client.post("/api/threads/nope/uploads", json={"filename": "a.png", "content_type": "image/png",
                                                                 "data_base64": PNG})
        assert r.status_code == 404


async def test_higgsfield_upload_puts_to_presigned_url_without_credentials():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.url.path == "/files/generate-upload-url":
            assert json.loads(req.content) == {"content_type": "image/webp"}
            return httpx.Response(200, json={"public_url": "https://cdn.example/in/p.webp",
                                             "upload_url": "https://storage.example/presigned?sig=1",
                                             "upload_headers": {"Content-Type": "image/webp", "x-amz-tagging": "retention=temporary"}})
        assert req.method == "PUT" and req.url.host == "storage.example"
        return httpx.Response(200)

    p = HiggsfieldProvider(Settings(internal_mode="local", hf_key="id:secret"), transport=httpx.MockTransport(handler))
    assert await p.upload(b"img", "image/webp") == "https://cdn.example/in/p.webp"
    gen, put = seen
    assert gen.headers["authorization"] == "Key id:secret"
    assert "authorization" not in put.headers  # credentials never reach the storage host
    assert put.headers["x-amz-tagging"] == "retention=temporary" and put.content == b"img"


async def test_higgsfield_upload_in_edge_mode_goes_through_the_worker_relay():
    seen = []
    presigned = "https://fnf-api-input-prod-1.s3.amazonaws.com/in/p.png?X-Amz-Signature=abc&x=1"

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.url.path == "/files/generate-upload-url":
            assert req.url.host == "higgsfield.internal"  # the Worker injects the key
            return httpx.Response(200, json={"public_url": "https://cdn.example/in/p.png", "upload_url": presigned,
                                             "upload_headers": {"Content-Type": "image/png"}})
        return httpx.Response(200)

    p = HiggsfieldProvider(Settings(internal_mode="edge"), transport=httpx.MockTransport(handler))
    assert await p.upload(b"img", "image/png") == "https://cdn.example/in/p.png"
    _, put = seen
    assert (put.method, put.url.host, put.url.path) == ("PUT", "hfupload.internal", "/")
    assert put.url.params["to"] == presigned  # signature survives the round trip intact
    assert "authorization" not in put.headers and put.content == b"img"


class Recorder:
    def __init__(self):
        self.submits = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if req.url.path.startswith("/estimate/"):
            return httpx.Response(200, json={"usd": "1.0"})
        self.submits.append((req.url.path, json.loads(req.content)))
        return httpx.Response(200, json={"status": "queued", "request_id": "r1"})


def _still(d, aid, url):
    d.app.assets[aid] = Asset(id=aid, thread_id=None, kind="image", status="completed", provider="higgsfield",
                              model="m", prompt="p", url=url, mode="live")


@pytest.mark.parametrize("model,field", [
    ("kling-video/v3.0/std/image-to-video", "last_image_url"),
    ("bytedance/seedance-2.5/image-to-video", "end_image_url"),
])
async def test_end_image_asset_maps_to_the_models_last_frame_field(model, field):
    rec = Recorder()
    d = install(media=HiggsfieldProvider(Settings(internal_mode="local", hf_key="id:secret"), transport=httpx.MockTransport(rec)))
    _still(d, "first", "https://cdn.example/first.png")
    _still(d, "last", "https://cdn.example/last.png")
    out = json.loads(await media.generate_media.ainvoke({"model": model, "prompt": "p", "image_asset_id": "first",
                                                         "end_image_asset_id": "last"}))
    assert "error" not in out, out
    _, body = rec.submits[0]
    assert body["image_url"] == "https://cdn.example/first.png" and body[field] == "https://cdn.example/last.png"
    assert await media.estimate_for_approval({"model": model, "prompt": "p", "image_asset_id": "first",
                                              "end_image_asset_id": "last"}) == 1.0
    for t in list(media._tasks):
        t.cancel()


async def test_end_frame_rejected_for_models_without_one_and_uploads_chain_as_references():
    rec = Recorder()
    d = install(media=HiggsfieldProvider(Settings(internal_mode="local", hf_key="id:secret"), transport=httpx.MockTransport(rec)))
    _still(d, "last", "https://cdn.example/last.png")
    out = json.loads(await media.generate_media.ainvoke({"model": "higgsfield-ai/soul/v2/standard", "prompt": "p",
                                                         "kind": "image", "end_image_asset_id": "last"}))
    assert "does not take an end frame" in out["error"] and not rec.submits
    d.app.assets["up"] = Asset(id="up", thread_id="t", kind="image", status="completed", provider="upload", model="upload",
                               prompt="lipstick.png", url="https://cdn.example/in/p.webp", mode="live")
    out = json.loads(await media.generate_media.ainvoke({"model": "marketing-studio/image", "prompt": "p", "kind": "image",
                                                         "reference_asset_ids": ["up"]}))
    assert "error" not in out, out
    assert rec.submits[0][1]["image_urls"] == ["https://cdn.example/in/p.webp"]
    for t in list(media._tasks):
        t.cancel()

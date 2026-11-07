import base64
import json

import httpx
import pytest

from ugecy.contracts import (
    ApprovalRecord,
    ApprovalRequest,
    Asset,
    AuditEntry,
    ConnectedAccount,
    Post,
    Source,
    ThreadSummary,
)
from ugecy.internal import InternalError, client
from ugecy.persistence import appstore as appstore_mod
from ugecy.persistence.appstore import D1AppStore, SqliteAppStore
from ugecy.persistence.edge import LocalEdgeBindings, html_to_text
from ugecy.persistence.kv import EdgeKV, MemoryKV, SqliteKV
from ugecy.settings import Settings


def S(**kw) -> Settings:
    return Settings(internal_mode=kw.pop("internal_mode", "test"), **kw)


def test_schema_copy_matches_migration():
    assert appstore_mod.REPO_MIGRATION.read_text() == appstore_mod.SCHEMA.read_text()


def test_client_raises_outside_edge():
    with pytest.raises(RuntimeError):
        client("state.internal", S())


async def test_appstore_crud_roundtrip():
    st = SqliteAppStore(S())
    await st.init()
    await st.upsert_thread(ThreadSummary(id="t1", title="A"))
    await st.upsert_thread(ThreadSummary(id="t1", title="B", status="running"))
    assert (await st.get_thread("t1")).title == "B" and len(await st.list_threads()) == 1

    await st.add_audit(AuditEntry(id="a1", thread_id="t1", actor="agent", action="x", status="ok", mode="live"))
    await st.add_audit(AuditEntry(id="a2", actor="system", action="y", status="ok", mode="live"))
    assert len(await st.list_audit()) == 2 and [a.id for a in await st.list_audit("t1")] == ["a1"]

    asset = Asset(id="s1", thread_id="t1", kind="image", status="queued", provider="p", model="m", prompt="q", mode="live")
    await st.upsert_asset(asset)
    await st.upsert_asset(asset.model_copy(update={"status": "completed", "url": "u", "estimated_usd": 0.5}))
    got = await st.get_asset("s1")
    assert got.status == "completed" and got.estimated_usd == 0.5 and (await st.list_assets("nope")) == []

    await st.upsert_post(Post(id="p1", thread_id="t1", account_id="acc", asset_id="s1", caption="c", ai_disclosure=True,
                              status="draft", mode="live"))
    assert (await st.get_post("p1")).ai_disclosure is True and await st.get_post("zz") is None

    await st.upsert_account(ConnectedAccount(id="acc", platform="tiktok", handle="@h", mode="live"))
    assert (await st.list_accounts())[0].handle == "@h"

    rec = ApprovalRecord(interrupt_id="i1", thread_id="t1", requests=[ApprovalRequest(
        tool="publish", agent="a", args={"k": [1, 2]}, description="d", allowed_decisions=["approve"])])
    await st.upsert_approval(rec)
    await st.upsert_approval(rec.model_copy(update={"status": "approved", "decided_at": "now"}))
    assert (await st.get_approval("i1")).requests[0].args == {"k": [1, 2]}
    assert [r.interrupt_id for r in await st.list_approvals("approved")] == ["i1"]
    assert await st.list_approvals("pending") == []

    src = Source(url="http://x", title="T", snippet="s")
    await st.add_source("t1", src)
    await st.add_source("t1", src)  # idempotent
    assert len(await st.list_sources("t1")) == 1

    await st.delete_thread("t1")
    assert await st.get_thread("t1") is None and await st.list_sources("t1") == []


async def test_sqlite_kv_roundtrip(tmp_path):
    s = S(internal_mode="local", data_dir=str(tmp_path))
    kv = SqliteKV(s)
    await kv.put("ns", {"a1": b"\x00\x01", "a2": b"2", "b": b"3"})
    kv2 = SqliteKV(s)  # new handle, same file
    assert await kv2.get("ns", "a") == {"a1": b"\x00\x01", "a2": b"2"}
    assert await kv2.delete("ns", "a") == 2 and list(await kv2.get("ns")) == ["b"]


async def test_memory_kv():
    kv = MemoryKV()
    await kv.put("n", {"x": b"1", "y": b"2"})
    assert await kv.delete("n", "x") == 1 and await kv.get("n") == {"y": b"2"}


def _http_stub(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://state.internal")


async def test_edge_kv_against_stub_transport():
    store: dict[str, bytes] = {}
    calls: list[int] = []

    def handler(req: httpx.Request) -> httpx.Response:
        b = json.loads(req.content)
        if req.url.path == "/kv/put":
            calls.append(len(b["items"]))
            for i in b["items"]:
                store[i["key"]] = base64.b64decode(i["value_b64"])
            return httpx.Response(200, json={"ok": True, "count": len(b["items"])})
        if req.url.path == "/kv/get":
            items = [{"key": k, "value_b64": base64.b64encode(v).decode()} for k, v in sorted(store.items())
                     if k.startswith(b["prefix"])]
            return httpx.Response(200, json={"items": items})
        return httpx.Response(400, json={"error": {"code": "bad", "message": "nope"}})

    kv = EdgeKV(S(internal_mode="edge"), _http_stub(handler))
    await kv.put("ckpt:t", {f"k{i:04d}": b"v" for i in range(450)})
    assert calls == [200, 200, 50]
    assert len(await kv.get("ckpt:t", "k00")) == 100
    with pytest.raises(InternalError) as e:
        await kv.delete("ckpt:t", "")
    assert e.value.code == "bad"


async def test_edge_kv_splits_by_bytes():
    sizes: list[int] = []

    def handler(req: httpx.Request) -> httpx.Response:
        sizes.append(len(json.loads(req.content)["items"]))
        return httpx.Response(200, json={"ok": True})

    kv = EdgeKV(S(internal_mode="edge"), _http_stub(handler))
    await kv.put("n", {f"k{i}": b"x" * 1_500_000 for i in range(4)})  # ~2 MB base64 each -> 2 per chunk
    assert sizes == [2, 2]


async def test_d1_appstore_posts_to_bindings():
    seen: list[dict] = []

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/d1/query"
        seen.append(json.loads(req.content))
        row = {"id": "t1", "title": "x", "created_at": "c", "updated_at": "u", "status": "idle"}
        return httpx.Response(200, json={"results": [row] if seen[-1]["sql"].startswith("SELECT") else [], "meta": {}})

    st = D1AppStore(S(internal_mode="edge"), _http_stub(handler))
    await st.init()
    await st.upsert_thread(ThreadSummary(id="t1", title="x"))
    assert "ON CONFLICT(id) DO UPDATE" in seen[0]["sql"] and seen[0]["params"][0] == "t1"
    assert (await st.get_thread("t1")).title == "x"


async def test_local_edge_bindings():
    page = "<html><head><title> Hi  there</title><style>p{}</style></head><body><script>x()</script><p>Hello\n  world</p></body></html>"
    assert html_to_text(page) == ("Hi there", "Hello\nworld")

    def handler(req: httpx.Request) -> httpx.Response:
        assert "Mozilla" in req.headers["user-agent"]
        return httpx.Response(200, text=page)

    e = LocalEdgeBindings(http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    r = await e.browser_markdown("http://a.test")
    assert r == {"url": "http://a.test", "title": "Hi there", "markdown": "Hello\nworld"}

    await e.vectors_upsert("n", [{"id": "1", "text": "funny cat video", "metadata": {"a": 1}},
                                 {"id": "2", "text": "tax law", "metadata": {}}])
    assert [m["id"] for m in await e.vectors_query("n", "cat videos funny")] == ["1"]
    assert await e.schedule_publish("p1", None) == "local-p1"
    assert (await e.media_ingest("a", "u", "image"))["playback_url"] == "u"


async def test_sqlite_appstore_persists_on_disk(tmp_path):
    s = S(internal_mode="local", data_dir=str(tmp_path))
    st = SqliteAppStore(s)
    await st.init()
    await st.upsert_thread(ThreadSummary(id="t9", title="disk"))
    st2 = SqliteAppStore(s)
    await st2.init()  # idempotent migration
    assert (await st2.get_thread("t9")).title == "disk"

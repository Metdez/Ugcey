import json
from types import SimpleNamespace

import httpx
import pytest

from ugecy.contracts import Asset, ProviderModes
from ugecy.deps import set_deps
from ugecy.integrations.storage import dropbox as dbx_mod
from ugecy.integrations.storage.dropbox import DropboxClient, set_dropbox
from ugecy.persistence.appstore import SqliteAppStore
from ugecy.settings import Settings
from ugecy.storage import backup


class FakeDropbox:
    """Scripted dropbox.internal: records calls, keeps a file set."""

    def __init__(self, connected=True, save="complete", missing=()):
        self.connected, self.save, self.files, self.calls, self.missing = connected, save, set(), [], list(missing)
        self.jobs = 0

    def __call__(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path
        body = json.loads(req.content or b"null") if req.method == "POST" else None
        self.calls.append((path, body))
        if path == "/_ugecy/status":
            return httpx.Response(200, json={"connected": self.connected, "account_name": "Op", "scopes": [],
                                             "missing_scopes": self.missing})
        if not self.connected:
            return httpx.Response(503, json={"error": {"code": "not_configured"}})
        if path == "/2/files/get_metadata":
            if body["path"] in self.files:
                return httpx.Response(200, json={".tag": "file", "path_display": body["path"]})
            return httpx.Response(409, json={"error_summary": "path/not_found/.."})
        if path == "/2/files/save_url":
            if self.save == "429" and self.jobs == 0:
                self.jobs += 1
                return httpx.Response(429, headers={"retry-after": "0"}, json={"error_summary": "too_many_requests/"})
            if self.save == "invalid":
                return httpx.Response(409, json={"error_summary": "invalid_url/"})
            if self.save in ("async", "async_fail"):
                return httpx.Response(200, json={".tag": "async_job_id", "async_job_id": "j1", "_path": body["path"]})
            self.files.add(body["path"])
            return httpx.Response(200, json={".tag": "complete", "path_display": body["path"]})
        if path == "/2/files/save_url/check_job_status":
            self.jobs += 1
            if self.jobs < 2:
                return httpx.Response(200, json={".tag": "in_progress"})
            if self.save == "async_fail":
                return httpx.Response(200, json={".tag": "failed", "failed": {".tag": "download_failed"}})
            saved = next(b["path"] for p, b in self.calls if p == "/2/files/save_url")
            self.files.add(saved)
            return httpx.Response(200, json={".tag": "complete", "path_display": saved})
        if path == "/2/files/list_folder":
            return httpx.Response(200, json={"entries": [{".tag": "file", "name": p.rsplit("/", 1)[-1], "path_display": p,
                                                          "size": 10, "server_modified": "2026-11-07T10:00:00Z"}
                                                         for p in sorted(self.files)], "has_more": False})
        if path == "/2/files/get_temporary_link":
            return httpx.Response(200, json={"link": "https://dl.dropboxusercontent.com/tmp/x"})
        return httpx.Response(403, json={"error": {"code": "path_not_allowed"}})


def asset(i="a1b2c3d4e5", kind="video", url="https://cdn.example/x/out.mp4", **kw):
    return Asset(id=i, thread_id="t", kind=kind, status="completed", provider="higgsfield", model="m",
                 prompt="Glow serum morning routine, cozy bathroom!", url=url, mode="live",
                 created_at="2026-11-07T10:00:00+00:00", **kw)


@pytest.fixture
async def env(monkeypatch):
    s = Settings(internal_mode="edge")
    app = SqliteAppStore(Settings(internal_mode="test"))
    await app.init()
    set_deps(SimpleNamespace(settings=s, app=app, modes=ProviderModes(storage="live")))
    monkeypatch.setattr(backup, "JOB_POLL_S", 0)
    monkeypatch.setattr(backup, "_SEM", None)

    def make(fake: FakeDropbox):
        async def nosleep(_):
            return None
        set_dropbox(DropboxClient(s, transport=httpx.MockTransport(fake), sleep=nosleep))
        return fake

    yield app, make
    set_dropbox(None)


def test_paths_are_readable_and_typed():
    assert backup.dropbox_path(asset()) == "/Ugecy/Videos/2026-11-07 glow serum morning routine cozy bathroom a1b2c3d4.mp4"
    img = asset(kind="image", url="https://cdn.example/a.webp?sig=1")
    assert backup.dropbox_path(img).startswith("/Ugecy/Images/") and img.id[:8] + ".webp" in backup.dropbox_path(img)
    assert backup.dropbox_path(asset(kind="image", url="https://cdn.example/noext")).endswith(".png")


async def test_backup_saves_and_is_idempotent(env):
    app, make = env
    fake = make(FakeDropbox())
    await app.upsert_asset(asset())
    r = await backup.backup_asset("a1b2c3d4e5")
    assert r["status"] == "saved" and r["dropbox_path"].endswith("a1b2c3d4.mp4")
    a = await app.get_asset("a1b2c3d4e5")
    assert (a.dropbox_status, a.dropbox_path) == ("saved", r["dropbox_path"])
    await app.upsert_asset(asset())  # a stale upsert (like media _save) must not wipe the Dropbox fields
    assert (await app.get_asset("a1b2c3d4e5")).dropbox_status == "saved"
    n = sum(p == "/2/files/save_url" for p, _ in fake.calls)
    await app.set_asset_dropbox("a1b2c3d4e5", None, None)
    assert (await backup.backup_asset("a1b2c3d4e5"))["status"] == "saved"  # file exists: no second upload
    assert sum(p == "/2/files/save_url" for p, _ in fake.calls) == n


async def test_async_job_polls_until_complete_and_429_retries(env):
    app, make = env
    make(FakeDropbox(save="async"))
    await app.upsert_asset(asset())
    assert (await backup.backup_asset("a1b2c3d4e5"))["status"] == "saved"
    make(FakeDropbox(save="429"))
    await app.upsert_asset(asset(i="zz9"))
    assert (await backup.backup_asset("zz9"))["status"] == "saved"


async def test_failures_are_recorded_honestly(env):
    app, make = env
    make(FakeDropbox(save="async_fail"))
    await app.upsert_asset(asset())
    r = await backup.backup_asset("a1b2c3d4e5")
    assert "download_failed" in r["error"] and (await app.get_asset("a1b2c3d4e5")).dropbox_status == "failed"
    make(FakeDropbox(save="invalid"))
    await app.upsert_asset(asset(i="b2"))
    assert "invalid_url" in (await backup.backup_asset("b2"))["error"]


async def test_not_connected_writes_nothing_and_reconcile_skips(env):
    app, make = env
    fake = make(FakeDropbox(connected=False))
    await app.upsert_asset(asset())
    assert "not connected" in (await backup.backup_asset("a1b2c3d4e5"))["error"].lower()
    assert (await app.get_asset("a1b2c3d4e5")).dropbox_status is None
    assert await backup.reconcile() == 0
    assert not any(p.startswith("/2/files/save_url") for p, _ in fake.calls)


async def test_reconcile_backfills_completed_unsaved_only(env):
    app, make = env
    fake = make(FakeDropbox())
    await app.upsert_asset(asset(i="v1"))
    await app.upsert_asset(asset(i="i1", kind="image", url="https://cdn.example/a.png"))
    await app.upsert_asset(asset(i="q1").model_copy(update={"status": "in_progress"}))
    await app.upsert_asset(asset(i="f1"))
    await app.set_asset_dropbox("f1", "/Ugecy/x", "failed")
    assert await backup.reconcile() == 2
    await backup.drain()
    assert len(fake.files) == 2 and await backup.reconcile() == 0
    assert await backup.reconcile(retry_failed=True) == 1
    await backup.drain()


async def test_uploaded_product_photos_never_reach_dropbox(env):
    # Dropbox files are offered for posting from the phone; an operator's reference photo must not be (#2 policy).
    app, make = env
    fake = make(FakeDropbox())
    await app.upsert_asset(asset(i="u1", kind="image", url="https://cdn.example/p.png").model_copy(update={"provider": "upload"}))
    assert await backup.reconcile() == 0
    assert "not saved" in (await backup.backup_asset("u1"))["error"]
    assert not fake.files and not any(p.startswith("/2/files") for p, _ in fake.calls)


async def test_tools(env):
    from ugecy.tools import dropbox as tools

    app, make = env
    make(FakeDropbox(missing=["files.content.write"]))
    await app.upsert_asset(asset())
    st = json.loads(await tools.dropbox_status.ainvoke({}))
    assert st["connected"] and st["missing_scopes"] == ["files.content.write"] and st["not_saved"] == 1
    saved = json.loads(await tools.save_to_dropbox.ainvoke({"asset_id": "a1b2c3d4e5"}))
    assert saved["status"] == "saved" and "Dropbox app" in saved["phone_steps"]
    media = json.loads(await tools.list_dropbox_media.ainvoke({"kind": "video"}))
    assert media["files"][0]["file_name"].endswith("a1b2c3d4.mp4")
    files = json.loads(await tools.browse_dropbox.ainvoke({}))["files"]
    assert files[0]["path"].startswith("/Ugecy/Videos/")
    make(FakeDropbox(connected=False))
    for t, args in ((tools.list_dropbox_media, {}), (tools.save_to_dropbox, {"asset_id": "x"}),
                    (tools.dropbox_backfill, {}), (tools.browse_dropbox, {})):
        assert "Dropbox not connected" in json.loads(await t.ainvoke(args))["error"]  # never fake files


async def test_assets_api_serves_dropbox_link_after_higgsfield_expiry(env):
    from ugecy.api import misc

    app, make = env
    make(FakeDropbox())
    await app.upsert_asset(asset(i="old").model_copy(update={"created_at": "2026-10-01T00:00:00+00:00"}))
    await app.upsert_asset(asset(i="new").model_copy(update={"created_at": "2099-01-01T00:00:00+00:00"}))
    for i in ("old", "new"):
        await app.set_asset_dropbox(i, f"/Ugecy/Videos/{i}.mp4", "saved")
    misc._LINKS.clear()
    out = {a.id: a for a in [await misc._durable(a) for a in await app.list_assets()]}
    assert out["old"].url.startswith("https://dl.dropboxusercontent.com") and out["new"].url.startswith("https://cdn.")


def test_client_singleton_reset():
    set_dropbox(None)
    assert dbx_mod._CLIENT is None


async def test_seed_adds_dropbox_playbook_to_existing_memory():
    from langgraph.store.memory import InMemoryStore

    from ugecy.graph import seed_store

    store = InMemoryStore()
    await store.aput(("ws", "memories"), "/AGENTS.md", {"content": "# Mine\n\n## Learned playbook\n- keep me", "encoding": "utf-8"})
    await seed_store(store, "ws")
    await seed_store(store, "ws")  # idempotent
    text = (await store.aget(("ws", "memories"), "/AGENTS.md")).value["content"]
    assert text.startswith("# Mine") and "- keep me" in text and text.count("- Media library:") == 1

import sys
import types

from _fakes_02_04 import make_agent, make_client, make_deps
from langchain_core.messages import AIMessage

from ugecy import registry
from ugecy.contracts import AuditEntry

AGENT = make_agent([AIMessage(content="ok", id="m")])


async def test_config_shape(monkeypatch):
    monkeypatch.setattr(registry, "AGENTS", {"research-analyst": registry.AgentModule(
        name="research-analyst", description="finds hooks", system_prompt="p", tools=["web_search"],
        model_role="research")})
    client, deps = make_client(AGENT)
    async with client:
        cfg = (await client.get("/api/config")).json()
        assert cfg["version"] == deps.settings.version and cfg["modes"]["publishing"] == "mock"
        assert {m["role"] for m in cfg["models"]} >= {"orchestrator", "fast", "embeddings"}
        assert len(cfg["starter_prompts"]) == 6
        names = {a["name"]: a for a in cfg["agents"]}
        assert names["orchestrator"]["model"] == deps.settings.model_orchestrator
        ra = names["research-analyst"]
        assert (ra["model"], ra["tools"], ra["enabled"]) == (deps.settings.model_research, ["web_search"], True)


async def test_health_and_error_envelope():
    client, _ = make_client(AGENT)
    async with client:
        assert (await client.get("/healthz")).json() == {"ok": True, "service": "ugecy-agent"}
        h = (await client.get("/api/healthz")).json()
        assert h["ok"] and h["version"]
        r = await client.get("/api/nope")
        assert r.status_code == 404 and set(r.json()["error"]) == {"code", "message"}
        r = await client.post("/api/threads/t/runs", json={})
        assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


async def test_memories_get_put():
    deps = make_deps()
    ws = deps.settings.workspace_id
    await deps.store.aput((ws, "memories"), "/AGENTS.md", {"content": "brand", "encoding": "utf-8"})
    await deps.store.aput(("global", "skills"), "/hooks/SKILL.md", {"content": "skill", "encoding": "utf-8"})
    client, _ = make_client(AGENT, deps)
    async with client:
        files = {f["path"]: f for f in (await client.get("/api/memories")).json()}
        assert files["/memories/AGENTS.md"]["editable"] and files["/memories/AGENTS.md"]["scope"] == "memories"
        assert not files["/skills/hooks/SKILL.md"]["editable"] and files["/skills/hooks/SKILL.md"]["content"] == "skill"

        r = await client.put("/api/memories", json={"path": "/memories/brand/voice.md", "content": "warm"})
        assert r.status_code == 200 and r.json()["path"] == "/memories/brand/voice.md"
        item = await deps.store.aget((ws, "memories"), "/brand/voice.md")
        assert item.value["content"] == "warm" and item.value["encoding"] == "utf-8"
        for bad in ("/skills/x.md", "/memories/", "/memories/../x", "memories/a.md"):
            assert (await client.put("/api/memories", json={"path": bad, "content": "x"})).status_code == 422


async def test_store_reads_and_no_seeded_accounts():
    deps = make_deps()
    await deps.app.add_audit(AuditEntry(id="a1", thread_id="t", actor="system", action="x", status="ok", mode="mock"))
    client, _ = make_client(AGENT, deps)
    async with client:
        assert (await client.get("/api/accounts")).json() == []  # nothing is ever seeded
        assert len((await client.get("/api/audit", params={"thread_id": "t"})).json()) == 1
        for path in ("assets", "approvals", "posts"):
            assert (await client.get(f"/api/{path}")).json() == []


async def test_device_screenshot():
    client, _ = make_client(AGENT)
    async with client:
        r = await client.get("/api/device/screenshot")
        assert r.headers["content-type"] == "image/jpeg" and r.content.startswith(b"\xff\xd8")


async def test_device_off_api():
    from ugecy.integrations.unavailable import OffDeviceProvider

    deps = make_deps()
    deps.device = OffDeviceProvider()
    client, _ = make_client(AGENT, deps)
    async with client:
        r = await client.get("/api/device/screenshot")
        assert r.status_code == 503 and r.json()["error"]["code"] == "not_connected"
        st = (await client.get("/api/device")).json()
        assert (st["provider"], st["mode"], st["devices"]) == ("glasshand", "off", [])


async def test_publish_job(monkeypatch):
    calls = []

    async def run_publish_job(post_id):
        calls.append(post_id)
        return {"post_id": post_id, "status": "published"}

    monkeypatch.setitem(sys.modules, "ugecy.tools.publishing", types.SimpleNamespace(run_publish_job=run_publish_job))
    client, _ = make_client(AGENT)
    async with client:
        assert (await client.post("/jobs/publish", json={"post_id": "p1"})).status_code == 400
        h = {"Idempotency-Key": "k1"}
        assert (await client.post("/jobs/publish", json={"post_id": "p1"}, headers=h)).json()["status"] == "published"
        await client.post("/jobs/publish", json={"post_id": "p1"}, headers=h)
        assert calls == ["p1"]
        assert (await client.post("/api/jobs/publish", json={"post_id": "p1"}, headers=h)).status_code == 404



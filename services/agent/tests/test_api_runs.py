import asyncio

import pytest
from _fakes_02_04 import CALLS, call, install_fake_graph, make_agent, make_client, sse
from langchain_core.messages import AIMessage

from ugecy.contracts import ThreadSummary


@pytest.fixture(autouse=True)
def _graph(monkeypatch):
    CALLS.clear()
    install_fake_graph(monkeypatch)


def simple_script():
    return [
        AIMessage(content="Writing a file", id="m1", tool_calls=[
            call("write_file", {"file_path": "/a.md", "content": "hello"}, "c1")]),
        AIMessage(content="All done", id="m2"),
    ]


def types(events):
    return [e["type"] for e in events]


async def test_thread_run_stream_and_state():
    client, deps = make_client(make_agent(simple_script()))
    async with client:
        thread = (await client.post("/api/threads", json={"title": "Skincare"})).json()
        tid = thread["id"]
        events = await sse(client, "POST", f"/api/threads/{tid}/runs", json={"message": "go"})
        t = types(events)
        assert t[0] == "run.started" and t[-1] == "run.completed" and events[-1]["status"] == "done"
        assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
        for expected in ("message.delta", "tool.started", "tool.completed", "files.updated", "message.completed"):
            assert expected in t
        assert "".join(e["text"] for e in events if e["type"] == "message.delta" and e["message_id"] == "m2") == "All done"

        state = (await client.get(f"/api/threads/{tid}")).json()
        assert state["thread"]["status"] == "idle" and state["thread"]["title"] == "Skincare"
        assert [m["role"] for m in state["messages"]] == ["user", "assistant", "tool", "assistant"]
        assert state["messages"][1]["tool_calls"][0]["name"] == "write_file"
        assert state["files"][0]["path"] == "/a.md" and state["files"][0]["size"] == 5
        assert state["pending_approval"] is None

        f = await client.get(f"/api/threads/{tid}/files", params={"path": "/a.md"})
        assert f.json() == {"path": "/a.md", "content": "hello"}
        assert (await client.get(f"/api/threads/{tid}/files", params={"path": "/nope"})).status_code == 404

        # run on an unknown thread creates it
        await sse(client, "POST", "/api/threads/new-one/runs", json={"message": "hello there"})
        assert (await deps.app.get_thread("new-one")).title == "hello there"

        assert (await client.delete(f"/api/threads/{tid}")).json() == {"ok": True}
        r = await client.get(f"/api/threads/{tid}")
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


async def test_reconnect_since_replays_buffer():
    client, _ = make_client(make_agent(simple_script()))
    async with client:
        events = await sse(client, "POST", "/api/threads/t1/runs", json={"message": "go"})
        again = await sse(client, "GET", "/api/threads/t1/stream", params={"since": 3})
        assert again == events[3:]
        assert (await sse(client, "GET", "/api/threads/t1/stream", headers={"Last-Event-ID": str(len(events) - 1)})) == events[-1:]
        assert (await client.get("/api/threads/none/stream")).status_code == 404


def interrupt_script(sub=False):
    task = call("task", {"subagent_type": "worker", "description": "publish"}, "t1")
    return [
        AIMessage(content="", id="m1", tool_calls=[task if sub else call("publish_post", {"caption": "hi"}, "c1")]),
        AIMessage(content="Published", id="m2"),
    ]


@pytest.mark.parametrize("decision,expected_call,final_status", [
    ({"type": "approve"}, ["hi"], "approved"),
    ({"type": "edit", "args": {"caption": "edited #ad"}}, ["edited #ad"], "edited"),
    ({"type": "reject", "message": "no"}, [], "rejected"),
])
async def test_interrupt_and_resume(decision, expected_call, final_status):
    client, deps = make_client(make_agent(interrupt_script()))
    async with client:
        events = await sse(client, "POST", "/api/threads/t1/runs", json={"message": "publish"})
        assert events[-1]["status"] == "interrupted"
        req = next(e for e in events if e["type"] == "approval.requested")
        assert req["requests"][0]["tool"] == "publish_post" and req["requests"][0]["args"] == {"caption": "hi"}
        assert CALLS == []
        assert (await deps.app.get_thread("t1")).status == "awaiting_approval"
        pending = (await client.get("/api/approvals", params={"status": "pending"})).json()
        assert pending[0]["interrupt_id"] == req["interrupt_id"]
        assert (await client.get("/api/threads/t1")).json()["pending_approval"]["interrupt_id"] == req["interrupt_id"]
        assert any(a.status == "pending" and a.action == "approval" for a in deps.app.audit)

        body = {"interrupt_id": req["interrupt_id"], "decisions": [decision]}
        resumed = await sse(client, "POST", "/api/threads/t1/resume", json=body)
        assert resumed[0]["type"] == "run.started" and resumed[-1]["status"] == "done"
        assert CALLS == expected_call
        assert (await deps.app.get_approval(req["interrupt_id"])).status == final_status
        assert deps.app.audit[-1].actor == "operator"
        assert (await deps.app.get_thread("t1")).status == "idle"
        # nothing pending any more
        r = await client.post("/api/threads/t1/resume", json=body)
        assert r.status_code == 404


async def test_resume_validation():
    client, _ = make_client(make_agent(interrupt_script()))
    async with client:
        ev = await sse(client, "POST", "/api/threads/t1/runs", json={"message": "x"})
        iid = next(e for e in ev if e["type"] == "approval.requested")["interrupt_id"]
        r = await client.post("/api/threads/t1/resume", json={"interrupt_id": iid, "decisions": []})
        assert r.status_code == 422
        r = await client.post("/api/threads/t1/resume", json={"interrupt_id": iid, "decisions": [{"type": "edit"}]})
        assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
        r = await client.post("/api/threads/t1/resume", json={"interrupt_id": "bogus", "decisions": [{"type": "approve"}]})
        assert r.status_code == 404


async def test_subagent_interrupt_and_events():
    sub = [AIMessage(content="", id="s1", tool_calls=[call("publish_post", {"caption": "sub"}, "sc1")]),
           AIMessage(content="sub done", id="s2")]
    client, _ = make_client(make_agent(interrupt_script(sub=True), sub))
    async with client:
        events = await sse(client, "POST", "/api/threads/t1/runs", json={"message": "x"})
        assert {"tool.started", "subagent.started", "approval.requested"} <= set(types(events))
        started = next(e for e in events if e["type"] == "subagent.started")
        assert started["subagent"] == "worker" and started["description"] == "publish"
        req = next(e for e in events if e["type"] == "approval.requested")
        assert req["agent"] == "worker" and req["parent_call_id"] == "t1"
        resumed = await sse(client, "POST", "/api/threads/t1/resume", json={
            "interrupt_id": req["interrupt_id"], "decisions": [{"type": "approve"}]})
        assert CALLS == ["sub"]
        assert "subagent.completed" in types(resumed) and resumed[-1]["status"] == "done"


async def test_conflict_and_cancel():
    gate = asyncio.Event()
    agent = make_agent(simple_script())
    real = agent.astream

    async def slow(*a, **kw):
        await gate.wait()
        async for p in real(*a, **kw):
            yield p

    agent.astream = slow
    client, deps = make_client(agent)
    async with client:
        await deps.app.upsert_thread(ThreadSummary(id="t1", title="x"))
        reader = asyncio.create_task(sse(client, "POST", "/api/threads/t1/runs", json={"message": "a"}))
        for _ in range(100):
            if (await deps.app.get_thread("t1")).status == "running":
                break
            await asyncio.sleep(0.01)
        r = await client.post("/api/threads/t1/runs", json={"message": "b"})
        assert r.status_code == 409 and r.json()["error"]["code"] == "run_active"
        assert (await client.post("/api/threads/t1/cancel")).json() == {"ok": True}
        events = await reader
        assert events[-1]["type"] == "run.completed" and events[-1]["status"] == "cancelled"
        assert (await deps.app.get_thread("t1")).status == "idle"
        assert (await client.post("/api/threads/t1/cancel")).json() == {"ok": False}


async def test_disconnect_does_not_cancel_run():
    client, deps = make_client(make_agent(simple_script()))
    async with client:
        async with client.stream("POST", "/api/threads/t1/runs", json={"message": "go"}) as r:
            await r.aiter_lines().__anext__()  # read one line, then drop the connection
        for _ in range(200):
            if (await deps.app.get_thread("t1")).status == "idle":
                break
            await asyncio.sleep(0.01)
        events = await sse(client, "GET", "/api/threads/t1/stream")
        assert events[-1]["status"] == "done"


async def test_model_error_becomes_error_events():
    agent = make_agent(simple_script())
    agent.astream = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("upstream 429"))  # sync raise on call
    client, deps = make_client(agent)
    async with client:
        events = await sse(client, "POST", "/api/threads/t1/runs", json={"message": "go"})
        assert types(events)[-2:] == ["error", "run.completed"]
        assert events[-2]["retryable"] is True and events[-1]["status"] == "error"
        assert (await deps.app.get_thread("t1")).status == "error"

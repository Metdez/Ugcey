from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langgraph.types import Interrupt

from ugecy import registry
from ugecy.stream.adapter import StreamAdapter

_ORCH = {"lc_agent_name": "ugecy-orchestrator"}


def part(type_, data, ns=()):
    return {"type": type_, "ns": ns, "data": data}


def types(events):
    return [e.type for e in events]


def test_text_reasoning_and_lifecycle():
    ad = StreamAdapter("t", "r", model="m")
    evs = ad.start()
    evs += ad.feed(part("messages", (AIMessageChunk(content="Hi ", id="a"), _ORCH)))
    evs += ad.feed(part("messages", (AIMessageChunk(content="", id="a", additional_kwargs={"reasoning_content": "hmm"}), _ORCH)))
    evs += ad.feed(part("messages", (AIMessageChunk(content="", id="a"), _ORCH)))  # empty: skipped
    evs += ad.finish()
    assert types(evs) == ["run.started", "message.delta", "reasoning.delta", "run.completed"]
    assert [e.seq for e in evs] == [1, 2, 3, 4]
    assert evs[0].model == "m" and evs[1].agent == "orchestrator" and evs[1].text == "Hi "
    assert evs[-1].status == "done"


def test_tool_calls_once_and_subagent_namespace():
    ad = StreamAdapter("t", "r")
    task = AIMessage(content="", id="m1", name="ugecy-orchestrator", tool_calls=[
        {"name": "task", "args": {"subagent_type": "worker", "description": "do it"}, "id": "c1"}])
    evs = ad.feed(part("updates", {"model": {"messages": [task]}}))
    assert ad.feed(part("updates", {"after_model": {"messages": [task]}})) == []  # no duplicate tool.started
    assert types(evs) == ["tool.started", "subagent.started"]
    assert (evs[1].subagent, evs[1].description) == ("worker", "do it")

    ns = ("tools:task-id",)
    md = {"lc_agent_name": "worker", "lc_subagent_tool_call_id": "c1"}
    sub = ad.feed(part("messages", (AIMessageChunk(content="x", id="s"), md), ns))[0]
    assert (sub.agent, sub.parent_call_id, sub.ns) == ("worker", "c1", ["tools:task-id"])
    # tool result inside the subagent picks up the learned agent / parent
    done = ad.feed(part("updates", {"tools": {"messages": [ToolMessage(content="ok", tool_call_id="sc", name="ls")]}}, ns))
    assert (done[0].type, done[0].agent, done[0].parent_call_id, done[0].status) == ("tool.completed", "worker", "c1", "ok")

    res = ToolMessage(content="y" * 3000, tool_call_id="c1", name="task")
    out = ad.feed(part("updates", {"tools": {"messages": [res]}}))
    assert types(out) == ["tool.completed", "subagent.completed"]
    assert len(out[0].output_preview) == 2000 and len(out[1].summary) == 600 and out[1].subagent == "worker"


def test_tool_error_status():
    ad = StreamAdapter("t", "r")
    err = ToolMessage(content="boom", tool_call_id="c", name="x", status="error")
    assert ad.feed(part("updates", {"tools": {"messages": [err]}}))[0].status == "error"


def test_values_only_on_change_at_root():
    ad = StreamAdapter("t", "r")
    state = {"todos": [{"content": "a", "status": "pending"}],
             "files": {"/a.md": {"content": "hello", "modified_at": "2026-01-01"}}}
    evs = ad.feed(part("values", state))
    assert types(evs) == ["todos.updated", "files.updated"]
    assert evs[1].files[0].size == 5 and evs[1].files[0].modified_at == "2026-01-01"
    assert ad.feed(part("values", state)) == []
    assert ad.feed(part("values", state, ("tools:x",))) == []
    state["todos"] = [{"content": "a", "status": "completed"}]
    assert types(ad.feed(part("values", state))) == ["todos.updated"]


def test_custom_events():
    ad = StreamAdapter("t", "r")
    src = {"url": "https://x.y", "title": "T", "platform": "web", "snippet": None}
    evs = ad.feed(part("custom", {"type": "source.added", "source": src}))
    assert evs[0].type == "source.added" and evs[0].source.url == "https://x.y"
    assert ad.feed(part("custom", {"type": "progress", "tool": "t", "message": "half"}))[0].message == "half"
    assert ad.feed(part("custom", {"type": "other"})) == []
    assert ad.feed(part("custom", {"type": "source.added", "source": {"bad": 1}})) == []


def test_interrupt_dedup_and_interrupted_finish(monkeypatch):
    monkeypatch.setattr(registry, "AGENTS", {"publisher": registry.AgentModule(
        name="publisher", description="d", system_prompt="p", tools=["publish_post"])})
    value = {"action_requests": [{"name": "publish_post", "args": {"c": 1}, "description": "needs approval"}],
             "review_configs": [{"action_name": "publish_post", "allowed_decisions": ["approve", "reject"]}]}
    ad = StreamAdapter("t", "r")
    sub = ad.feed(part("updates", {"__interrupt__": (Interrupt(value=value, id="i1"),)}, ("tools:x",)))
    root = ad.feed(part("updates", {"__interrupt__": (Interrupt(value=value, id="i1"),)}))
    assert root == [] and len(sub) == 1
    req = sub[0].requests[0]
    assert (sub[0].interrupt_id, req.tool, req.agent, req.allowed_decisions) == ("i1", "publish_post", "publisher", ["approve", "reject"])
    assert ad.finish()[0].status == "interrupted"


def test_failure_retryable():
    ad = StreamAdapter("t", "r")
    evs = ad.fail(RuntimeError("HTTP 429 rate limited"))
    assert (evs[0].type, evs[0].retryable, evs[1].status) == ("error", True, "error")
    assert StreamAdapter("t", "r").fail(ValueError("bad"))[0].retryable is False
    assert StreamAdapter("t", "r").fail(TimeoutError())[0].retryable is True

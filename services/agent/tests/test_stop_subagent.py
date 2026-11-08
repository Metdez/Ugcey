from types import SimpleNamespace

from ugecy.middleware import stop


def _cfg(monkeypatch, call_id: str | None, thread_id: str = "t1"):
    import langgraph.config as lgc

    monkeypatch.setattr(lgc, "get_config", lambda: {"metadata": {"lc_subagent_tool_call_id": call_id},
                                                    "configurable": {"thread_id": thread_id}})


async def test_stopped_subagent_ends_and_skips_tools(monkeypatch):
    stop.clear("t1")
    _cfg(monkeypatch, "call-1")
    mw = stop.StopMiddleware()
    assert await mw.abefore_model({}, None) is None  # not stopped yet

    async def handler(req):
        return "ran"

    req = SimpleNamespace(tool_call={"id": "tc1", "name": "device_tap"})
    assert await mw.awrap_tool_call(req, handler) == "ran"
    stop.request_stop("t1", "call-1")
    out = await mw.abefore_model({}, None)
    assert out["jump_to"] == "end" and out["messages"][0].content == stop.STOPPED_TEXT
    msg = await mw.awrap_tool_call(req, handler)
    assert msg.content == stop.STOPPED_TEXT and msg.tool_call_id == "tc1"


async def test_other_subagents_and_orchestrator_keep_running(monkeypatch):
    stop.clear("t1")
    stop.request_stop("t1", "call-1")
    _cfg(monkeypatch, "call-2")
    assert await stop.StopMiddleware().abefore_model({}, None) is None
    _cfg(monkeypatch, None)  # orchestrator has no subagent call id
    assert stop.is_stopped() is False

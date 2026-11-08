"""The phone agent looks a failed step up with web_search (Firecrawl) before trying again."""
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from tests._fakes_02_05 import fake_deps, fake_model, fake_models, install_registry
from ugecy.contracts import ProviderModes
from ugecy.graph import RunContext, _subagents, build_agent
from ugecy.integrations.research.web import WebResearchProvider
from ugecy.integrations.unavailable import DEVICE_OFF
from ugecy.middleware.stuck import HINT, SearchWhenStuckMiddleware, failed
from ugecy.settings import Settings


def _msg(content: str, status: str = "success") -> ToolMessage:
    return ToolMessage(content=content, tool_call_id="1", status=status)


async def _run(tool: str, content: str) -> str:
    async def handler(_):
        return _msg(content)
    req = SimpleNamespace(tool_call={"name": tool, "args": {}, "id": "1"})
    return (await SearchWhenStuckMiddleware().awrap_tool_call(req, handler)).content


def test_failed_reads_every_error_shape():
    for bad in ["error: no active device session", '{"error": "submit failed"}', '{"ok": false, "error": "failed"}']:
        assert failed(_msg(bad)), bad
    assert failed(_msg("boom", status="error"))
    for ok in ['{"ok": true, "error": null}', '{"mode": "live", "results": 0, "note": "no results"}',
               "ok: URL submitted in Spotlight", '{"url": "u"}\n\n# page with {"error": 1} inside']:
        assert not failed(_msg(ok)), ok


async def test_hint_only_on_failures_search_can_help():
    assert (await _run("device_tap", '{"ok": false, "error": "failed"}')).endswith(HINT)
    assert await _run("device_tap", '{"ok": true}') == '{"ok": true}'
    for tool, content in [("device_screenshot", f"error: {DEVICE_OFF}"), ("device_tap", '{"ok": false, "error": "control_taken"}'),
                          ("web_search", json.dumps({"mode": "live", "results": 0, "error": "search failed: HTTPError"}))]:
        assert await _run(tool, content) == content, content


def test_wired_for_agents_with_web_search_while_search_is_live(monkeypatch):
    install_registry(monkeypatch)
    deps = fake_deps()

    def stuck(): return {s["name"] for s in _subagents(deps, fake_models())
                         if any(isinstance(m, SearchWhenStuckMiddleware) for m in s["middleware"])}
    assert stuck() == set()  # search off: nothing to look things up with
    deps.modes = ProviderModes(research="live")
    assert stuck() == {"device-operator", "research-analyst"}


async def test_device_operator_searches_after_a_failed_tap(monkeypatch):
    install_registry(monkeypatch)
    deps = fake_deps()
    deps.modes = ProviderModes(research="live")
    tap = AIMessage(content="", tool_calls=[{"name": "device_tap", "id": "d1", "args": {}}])
    phone = fake_model(tap, "Looked it up.")
    seen = []
    orig = type(phone)._generate

    def spy(self, messages, *a, **k):
        if self is phone:
            seen.append(messages)
        return orig(self, messages, *a, **k)
    monkeypatch.setattr(type(phone), "_generate", spy)
    from ugecy import registry
    monkeypatch.setattr(registry.TOOLS["device_tap"].tool, "func", lambda **_: '{"ok": false, "error": "failed"}')
    models = fake_models(fake_model(AIMessage(content="", tool_calls=[{"name": "task", "id": "k1", "args": {
        "description": "Save the video to Photos", "subagent_type": "device-operator"}}]), "Done."))
    models["research"] = phone  # device-operator's model role
    await build_agent(deps, models).ainvoke({"messages": [{"role": "user", "content": "save it"}]},
                                           {"configurable": {"thread_id": "s"}}, context=RunContext())
    tool_result = next(m for m in seen[-1] if isinstance(m, ToolMessage) and m.name == "device_tap")
    assert tool_result.content.endswith(HINT) and "web_search" in tool_result.content


@pytest.mark.parametrize("name", ["FIRECRAWL_API_KEY", "FIRECRAWL_API"])
def test_firecrawl_key_from_either_env_name(monkeypatch, name):
    monkeypatch.setenv(name, "fc-test")
    assert WebResearchProvider(Settings()).mode == "live"

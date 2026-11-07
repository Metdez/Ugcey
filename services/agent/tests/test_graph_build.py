import re

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from tests._fakes_02_05 import (
    FakeApp,
    fake_deps,
    fake_model,
    fake_models,
    install_registry,
)
from ugecy import registry
from ugecy.deps import set_deps
from ugecy.graph import RunContext, _subagents, build_agent, seed_store
from ugecy.middleware.audit import AuditMiddleware

SIDE_EFFECT_TOOLS = {"generate_media", "publish_post", "device_commit", "device_tap", "device_swipe",
                     "device_type", "device_start_session"}
EXPECTED = {
    "research-analyst": {"web_search", "fetch_page", "remember_pattern", "search_patterns", "device_status", "device_start_session",
                         "device_screenshot", "device_scroll", "device_back", "device_observe", "device_tap", "device_swipe",
                         "device_next_post", "device_type", "device_home"},
    "creative-strategist": {"search_patterns"},
    "compliance-critic": {"compliance_check"},
    "production-coordinator": {"list_media_models", "estimate_media_cost", "generate_media", "check_media_job"},
    "publishing-coordinator": {"list_connected_accounts", "publish_post", "get_post_status"},
    "device-operator": {"device_status", "device_screenshot", "device_start_session", "device_tap", "device_swipe",
                        "device_scroll", "device_back", "device_open_url", "device_type", "device_home", "device_commit"},
    "analytics-analyst": {"get_post_metrics", "search_patterns", "remember_pattern"},
}


@pytest.fixture
def reg(monkeypatch):
    install_registry(monkeypatch)


def test_seven_agents_registered(reg):
    assert set(registry.AGENTS) == set(EXPECTED)
    assert all(a.system_prompt.strip() and a.description for a in registry.AGENTS.values())


def test_each_subagent_has_exactly_its_tools(reg):
    specs = {s["name"]: s for s in _subagents(fake_deps(), fake_models())}
    for name, tools in EXPECTED.items():
        assert {t.name for t in specs[name]["tools"]} == tools, name


def test_general_purpose_has_no_tools(reg):
    gp = next(s for s in _subagents(fake_deps(), fake_models()) if s["name"] == "general-purpose")
    assert gp["tools"] == []


def test_interrupt_map_has_only_paid_generation(reg):
    assert set(registry.interrupt_map()) == {"generate_media"}


def test_disabled_agent_is_dropped(reg):
    deps = fake_deps()
    deps.settings = deps.settings.model_copy(update={"disabled_agents": "device-operator"})
    assert "device-operator" not in {s["name"] for s in _subagents(deps, fake_models())}


async def test_graph_runs_with_todos_and_context(reg):
    plan = AIMessage(content="", tool_calls=[{"name": "write_todos", "id": "t1", "args": {
        "todos": [{"content": "Research", "status": "in_progress"}]}}])
    agent = build_agent(fake_deps(), fake_models(fake_model(plan, "All done.")))
    cfg = {"configurable": {"thread_id": "t"}}
    out = await agent.ainvoke({"messages": [{"role": "user", "content": "go"}]}, cfg,
                              context=RunContext(workspace_id="ws1"))
    assert out["todos"][0]["content"] == "Research"
    assert out["messages"][-1].content == "All done."
    assert any(isinstance(m, ToolMessage) and m.name == "write_todos" for m in out["messages"])


async def test_audit_writes_entry_and_survives_failure(reg):
    class Req:
        def __init__(self):
            self.tool_call = {"name": "generate_media", "args": {"prompt": "x" * 500}, "id": "1"}

    async def handler(_):
        return ToolMessage(content="ok", tool_call_id="1")

    app = FakeApp()
    set_deps(fake_deps(app))
    await AuditMiddleware().awrap_tool_call(Req(), handler)
    e = app.entries[0]
    assert (e.actor, e.action, e.tool, e.status, e.mode) == ("agent", "tool_call", "generate_media", "ok", "live")
    assert len(e.detail) == 300
    set_deps(fake_deps(FakeApp(fail=True)))
    assert (await AuditMiddleware().awrap_tool_call(Req(), handler)).content == "ok"  # audit failure is swallowed


async def test_seed_store_writes_skills_and_keeps_existing_memory():
    store = fake_deps().store
    await seed_store(store, "ws1")
    names = {i.key for i in await store.asearch(("global", "skills"))}
    assert names == {f"/{n}/SKILL.md" for n in (
        "ugc-hook-extraction", "short-form-script-structure", "script-critic-rubric",
        "higgsfield-prompting", "platform-publishing-checklist", "ftc-disclosure", "phone-research")}
    assert (await store.aget(("ws1", "memories"), "/AGENTS.md")).value["content"].startswith("# Brand voice")
    await store.aput(("ws1", "memories"), "/AGENTS.md", {"content": "mine", "encoding": "utf-8"})
    await seed_store(store, "ws1")
    assert (await store.aget(("ws1", "memories"), "/AGENTS.md")).value["content"] == "mine"


def test_skill_frontmatter_is_valid():
    from importlib.resources import files
    root = files("ugecy").joinpath("skills")
    skills = [d for d in root.iterdir() if d.is_dir() and not d.name.startswith("_")]
    assert len(skills) == 7
    for d in skills:
        head = d.joinpath("SKILL.md").read_text("utf-8").split("---")[1]
        assert re.search(rf"^name: {d.name}$", head, re.MULTILINE)
        assert len(re.search(r"^description: (.+)$", head, re.MULTILINE).group(1)) <= 1024


async def test_orchestrator_can_delegate_to_registered_subagent(reg):
    call = AIMessage(content="", tool_calls=[{"name": "task", "id": "k1", "args": {
        "description": "Find 3 patterns", "subagent_type": "research-analyst"}}])
    models = fake_models(fake_model(call, "Delegated."))
    models["research"] = fake_model("Wrote /research/summary.md")
    agent = build_agent(fake_deps(), models)
    out = await agent.ainvoke({"messages": [{"role": "user", "content": "research"}]},
                              {"configurable": {"thread_id": "d"}}, context=RunContext())
    task_result = next(m for m in out["messages"] if isinstance(m, ToolMessage) and m.name == "task")
    assert "summary.md" in task_result.content


def test_research_gets_its_own_clean_stop_cap(reg):
    from langchain.agents.middleware import ModelCallLimitMiddleware

    def cap(spec):
        lims = [m for m in spec["middleware"] if isinstance(m, ModelCallLimitMiddleware)]
        assert len(lims) == 1 and lims[0].exit_behavior == "end"
        return lims[0].run_limit
    deps = fake_deps()
    specs = {s["name"]: s for s in _subagents(deps, fake_models()) if "middleware" in s}
    assert cap(specs["research-analyst"]) == deps.settings.max_model_calls_research == 200
    assert all(cap(s) == deps.settings.max_model_calls_per_subagent for n, s in specs.items() if n != "research-analyst")

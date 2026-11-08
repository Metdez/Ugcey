import json
from typing import ClassVar

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from tests._fakes_02_05 import (
    FakeChat,
    fake_deps,
    fake_model,
    fake_models,
    install_registry,
)
from ugecy.graph import ORCHESTRATOR, RunContext, _subagents, build_agent
from ugecy.memory import experience
from ugecy.middleware.memory import ExperienceMiddleware, LiveMemoryMiddleware
from ugecy.middleware.stuck import StuckMiddleware, detect, nudge

NS = ("default", "memories")


def call(name, args=None, cid=None):
    cid = cid or f"{name}-{id(args)}-{call.n}"
    call.n += 1
    return AIMessage(content="", tool_calls=[{"name": name, "args": args or {}, "id": cid}]), cid


call.n = 0


def turn(name, result, args=None, status="success"):
    ai, cid = call(name, args)
    return [ai, ToolMessage(content=result, tool_call_id=cid, name=name, status=status)]


def convo(*turns):
    return [HumanMessage(content="do the thing"), *[m for t in turns for m in t]]


def screen(app="TikTok", labels=("For You", "Search", "Profile")):
    return json.dumps({"app": app, "screen": "feed", "elements": [{"label": x, "kind": "button"} for x in labels]})


def test_three_errors_in_a_row_is_stuck():
    s = detect(convo(*[turn("device_tap", "error: no active approved device session", {"x": i / 10, "y": 0.5})
                       for i in range(3)]))
    assert s.kind == "errors" and s.tool == "device_tap" and "no active approved device session" in s.query


def test_same_call_same_result_is_stuck_but_progress_is_not():
    assert detect(convo(*[turn("device_tap", f'{{"ok":true,"steps_used":{i}}}', {"x": 0.5, "y": 0.5})
                          for i in range(3)])).kind == "repeat"  # steps_used is ignored
    assert detect(convo(*[turn("device_scroll", screen(labels=(f"post {i}",)), {"direction": "down"})
                          for i in range(5)])) is None  # same call, new content each time: progress
    assert detect(convo(*[turn("check_media_job", '{"status":"running"}', {"job_id": "j"}) for _ in range(6)])) is None


def test_unchanged_screen_while_acting_is_stuck():
    turns = []
    for i in range(3):
        turns += [turn("device_tap", f'{{"ok":true,"steps_used":{i}}}', {"x": 0.1 * i, "y": 0.9}),
                  turn("device_screenshot", screen())]
    assert detect(convo(*turns)).kind == "no_change"
    assert detect(convo(*[turn("device_screenshot", screen(labels=(str(i),))) for i in range(3)])) is None


def test_web_lookup_resets_the_window():
    stuck = [turn("device_tap", "error: x", {"x": i}) for i in range(3)]
    assert detect(convo(*stuck)) is not None
    assert detect(convo(*stuck, turn("web_search", "results"))) is None
    assert detect(convo(*stuck, turn("web_search", "results"), *stuck)) is not None  # stuck again after searching


def test_nudge_wording():
    s = detect(convo(*[turn("device_tap", "error: x", {"x": i}) for i in range(3)]))
    assert "`web_search`" in nudge(s, True) and "research-analyst" in nudge(s, False)
    assert "<stuck_recovery>" in nudge(s, True)


def test_episode_from_last_run():
    msgs = [HumanMessage(content="old"), AIMessage(content="old answer"),
            *convo(turn("device_tap", "error: boom", {"x": 1}), turn("device_screenshot", screen())),
            AIMessage(content="Opened the profile.")]
    e = experience.episode_from(msgs, "device-operator", ["repeat: x"])
    assert e["task"] == "do the thing" and e["outcome"] == "errors" and e["result"] == "Opened the profile."
    assert e["tools"] == {"device_tap": 1, "device_screenshot": 1} and e["failed"] == {"device_tap": 1}
    md = experience.episode_md(e)
    assert "device_tap×1 (1 failed)" in md and "Stuck: repeat: x" in md and "Error: device_tap: error: boom" in md
    stopped = experience.episode_from([HumanMessage(content="t"), AIMessage(content="Stopped by the operator.")], "a")
    assert stopped["outcome"] == "stopped"


async def test_record_appends_episode_and_merges_lessons():
    store = fake_deps().store
    ep = experience.episode_from(convo(turn("web_search", "r")), "research-analyst")
    await experience.record(store, "default", ep, fake_model("- Search TikTok Creative Center first\n- Use 30s hooks"))
    lessons = (await store.aget(NS, "/agents/research-analyst.md")).value["content"]
    assert "- Search TikTok Creative Center first" in lessons and lessons.startswith("# research-analyst lessons")
    for _ in range(experience.KEEP_EPISODES + 3):
        await experience.record(store, "default", ep, None)
    log = (await store.aget(NS, "/episodes/research-analyst.md")).value["content"]
    assert log.count("\n## ") == experience.KEEP_EPISODES


async def test_lesson_merge_failure_keeps_episode_and_lessons():
    class Boom:
        async def ainvoke(self, _):
            raise RuntimeError("model down")

    store = fake_deps().store
    ep = experience.episode_from(convo(turn("device_tap", "ok")), "device-operator")
    await experience.record(store, "default", ep, fake_model("- keep me"))
    await experience.record(store, "default", ep, Boom())
    assert "- keep me" in (await store.aget(NS, "/agents/device-operator.md")).value["content"]
    assert (await store.aget(NS, "/episodes/device-operator.md")).value["content"].count("\n## ") == 2


async def test_chat_only_turn_records_episode_without_lessons():
    store = fake_deps().store
    ep = experience.episode_from([HumanMessage(content="hi"), AIMessage(content="hello")], ORCHESTRATOR)
    await experience.record(store, "default", ep, fake_model("- nothing"))
    assert await store.aget(NS, f"/agents/{ORCHESTRATOR}.md") is None
    assert await store.aget(NS, f"/episodes/{ORCHESTRATOR}.md") is not None


@pytest.fixture
def reg(monkeypatch):
    install_registry(monkeypatch)


def test_every_agent_gets_memory_experience_and_stuck(reg):
    for spec in _subagents(fake_deps(), fake_models()):
        names = {type(m).__name__ for m in spec["middleware"]}
        if spec["name"] == "general-purpose":
            continue
        assert {"LiveMemoryMiddleware", "ExperienceMiddleware", "StuckMiddleware"} <= names, spec["name"]
        mem = next(m for m in spec["middleware"] if isinstance(m, LiveMemoryMiddleware))
        assert mem.sources == ["/memories/AGENTS.md", f"/memories/agents/{spec['name']}.md"]
        assert f"/memories/agents/{spec['name']}.md" in spec["system_prompt"]
        assert next(m for m in spec["middleware"] if isinstance(m, StuckMiddleware)).has_lookup


class Recorder(FakeChat):
    systems: ClassVar[list] = []

    def _generate(self, messages, *a, **kw):
        type(self).systems.append(next((m.text for m in messages if m.type == "system"), ""))
        return super()._generate(messages, *a, **kw)


async def test_end_to_end_stuck_nudge_memory_and_reload(reg):
    Recorder.systems = []
    taps = [AIMessage(content="", tool_calls=[{"name": "device_tap", "id": f"tap{i}", "args": {}}]) for i in range(3)]
    research = Recorder(messages=iter([*taps, AIMessage(content="Gave up and reported.")]))
    deps = fake_deps()
    models = fake_models(fake_model(
        AIMessage(content="", tool_calls=[{"name": "task", "id": "k1", "args": {
            "description": "Open TikTok search", "subagent_type": "device-operator"}}]), "Delegated."))
    models["research"], models["critic"] = research, fake_model(*["- Tapping Search again does nothing; search first"] * 4)
    await deps.store.aput(NS, "/agents/device-operator.md", {"content": "- LESSON-ONE", "encoding": "utf-8"})
    agent = build_agent(deps, models)
    await agent.ainvoke({"messages": [{"role": "user", "content": "go"}]}, {"configurable": {"thread_id": "e2e"}},
                        context=RunContext())
    await experience.drain()
    assert all("LESSON-ONE" in s for s in Recorder.systems)  # own lessons loaded into the subagent prompt
    assert not any("<stuck_recovery>" in s for s in Recorder.systems[:3])
    assert "<stuck_recovery>" in Recorder.systems[3] and "`web_search`" in Recorder.systems[3]
    ep = (await deps.store.aget(NS, "/episodes/device-operator.md")).value["content"]
    assert "Task: Open TikTok search" in ep and "device_tap×3" in ep and "Stuck: repeat" in ep
    lessons = (await deps.store.aget(NS, "/agents/device-operator.md")).value["content"]
    assert "- Tapping Search again does nothing" in lessons
    assert await deps.store.aget(NS, f"/episodes/{ORCHESTRATOR}.md") is not None


async def test_experience_middleware_never_raises():
    mw = ExperienceMiddleware("x", None, None)
    assert await mw.aafter_agent({"messages": []}, None) is None
    mw = ExperienceMiddleware("x", object(), None)
    assert await mw.aafter_agent({"messages": "not a list"}, None) is None

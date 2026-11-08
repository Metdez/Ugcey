import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from ugecy.persistence import build_checkpointer, build_store
from ugecy.persistence.kv import MemoryKV


class S(TypedDict):
    n: int
    messages: Annotated[list[str], operator.add]


def _graph(saver, with_interrupt=False):
    def step(s: S):
        return {"n": s["n"] + 1, "messages": [f"step{s['n'] + 1}"]}

    def ask(s: S):
        answer = interrupt({"q": "ok?"})
        return {"messages": [f"answer:{answer}"]}

    g = StateGraph(S)
    g.add_node("step", step)
    g.add_edge(START, "step")
    if with_interrupt:
        g.add_node("ask", ask)
        g.add_edge("step", "ask")
        g.add_edge("ask", END)
    else:
        g.add_edge("step", END)
    return g.compile(checkpointer=saver)


CFG = {"configurable": {"thread_id": "t1"}}


async def test_state_and_history_survive_restart():
    kv = MemoryKV()
    g1 = _graph(build_checkpointer(kv))
    await g1.ainvoke({"n": 0, "messages": ["hi"]}, CFG)
    await g1.ainvoke({"n": 5, "messages": []}, CFG)
    history1 = [c.config["configurable"]["checkpoint_id"] async for c in g1.aget_state_history(CFG)]

    g2 = _graph(build_checkpointer(kv))  # simulated restart: fresh saver, same KV
    state = await g2.aget_state(CFG)
    assert state.values["messages"] == ["hi", "step1", "step6"]
    assert [c.config["configurable"]["checkpoint_id"] async for c in g2.aget_state_history(CFG)] == history1
    out = await g2.ainvoke({"n": 10, "messages": []}, CFG)
    assert out["messages"][-1] == "step11" and out["n"] == 11


async def test_interrupt_inside_a_subgraph_resumes_after_restart():
    def sub():
        g = StateGraph(S)
        g.add_node("ask", lambda s: {"messages": [f"sub:{interrupt('ok?')}"]})
        g.add_edge(START, "ask")
        g.add_edge("ask", END)
        return g.compile()

    def parent(saver):
        g = StateGraph(S)
        g.add_node("step", lambda s: {"n": s["n"] + 1, "messages": ["step"]})
        g.add_node("child", sub())
        g.add_edge(START, "step")
        g.add_edge("step", "child")
        g.add_edge("child", END)
        return g.compile(checkpointer=saver)

    control = parent(InMemorySaver())  # the same run with no restart
    await control.ainvoke({"n": 0, "messages": []}, CFG)
    kv = MemoryKV()
    await parent(build_checkpointer(kv)).ainvoke({"n": 0, "messages": []}, CFG)
    assert any(k.startswith('c|["child:') for k in await kv.get("ckpt:t1"))  # the subgraph has its own namespace

    g2 = parent(build_checkpointer(kv))
    assert (await g2.aget_state(CFG)).tasks[0].interrupts
    out = await g2.ainvoke(Command(resume="yes"), CFG)
    assert out == await control.ainvoke(Command(resume="yes"), CFG)
    assert out["messages"][-1] == "sub:yes"


async def test_interrupt_resumes_after_restart():
    kv = MemoryKV()
    g1 = _graph(build_checkpointer(kv), with_interrupt=True)
    await g1.ainvoke({"n": 0, "messages": []}, CFG)
    assert (await g1.aget_state(CFG)).next == ("ask",)

    g2 = _graph(build_checkpointer(kv), with_interrupt=True)
    state = await g2.aget_state(CFG)
    assert state.next == ("ask",) and state.tasks[0].interrupts
    out = await g2.ainvoke(Command(resume="yes"), CFG)
    assert out["messages"] == ["step1", "answer:yes"]


async def test_delete_thread_clears_kv_and_isolated_threads():
    kv = MemoryKV()
    g = _graph(build_checkpointer(kv))
    await g.ainvoke({"n": 0, "messages": []}, CFG)
    other = {"configurable": {"thread_id": "t2"}}
    await g.ainvoke({"n": 0, "messages": []}, other)
    saver = build_checkpointer(kv)
    await saver.adelete_thread("t1")
    assert not await kv.get("ckpt:t1") and await kv.get("ckpt:t2")
    assert await _graph(build_checkpointer(kv)).aget_state(CFG) is not None
    assert (await _graph(build_checkpointer(kv)).aget_state(CFG)).values == {}


def test_is_inmemory_subclass():
    assert isinstance(build_checkpointer(MemoryKV()), InMemorySaver)


async def test_store_put_restart_search():
    kv = MemoryKV()
    s1 = await build_store(kv)
    await s1.aput(("default", "memories"), "/AGENTS.md", {"content": "brand voice: playful"})
    await s1.aput(("default", "memories"), "/old.md", {"content": "x"})
    await s1.adelete(("default", "memories"), "/old.md")

    s2 = await build_store(kv)
    hits = await s2.asearch(("default", "memories"))
    assert [h.key for h in hits] == ["/AGENTS.md"]
    assert hits[0].value["content"] == "brand voice: playful"
    assert hits[0].created_at and (await s2.aget(("default", "memories"), "/AGENTS.md")).value

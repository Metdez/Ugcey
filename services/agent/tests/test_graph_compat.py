from langchain.agents.middleware.types import ModelResponse
from langchain_core.messages import AIMessage, HumanMessage

from ugecy.middleware.compat import CompatMiddleware, parse_text_tool_calls, strip_think


def test_strip_think_removes_closed_and_open_blocks():
    assert strip_think("<think>plan</think>\nHello") == "Hello"
    assert strip_think("Hi <think>never closed") == "Hi"


def test_parse_text_tool_calls():
    text = 'ok <tool_call>{"name": "web_search", "arguments": {"query": "x"}}</tool_call>'
    rest, calls = parse_text_tool_calls(text, {"web_search"})
    assert rest == "ok" and calls[0]["name"] == "web_search" and calls[0]["args"] == {"query": "x"}
    assert parse_text_tool_calls(text, {"other"})[1] == []  # unknown tool ignored
    assert parse_text_tool_calls("<tool_call>{bad}</tool_call>")[1] == []


class _Req:
    def __init__(self, messages, tools):
        self.messages, self.tools = messages, tools

    def override(self, **kw):
        return _Req(kw.get("messages", self.messages), self.tools)


class _Tool:
    name = "web_search"


async def test_middleware_cleans_response_and_parses_call():
    reply = AIMessage(content='<think>x</think><tool_call>{"name":"web_search","arguments":{"query":"q"}}</tool_call>')

    async def handler(_):
        return ModelResponse(result=[reply])

    out = await CompatMiddleware().awrap_model_call(_Req([HumanMessage(content="go")], [_Tool()]), handler)
    assert out.result[0].tool_calls[0]["name"] == "web_search" and out.result[0].content == ""


async def test_narration_is_nudged_once():
    calls = []

    async def handler(req):
        calls.append(req)
        text = "I'll call web_search now." if len(calls) == 1 else "I'll call web_search again."
        return ModelResponse(result=[AIMessage(content=text)])

    await CompatMiddleware().awrap_model_call(_Req([HumanMessage(content="go")], [_Tool()]), handler)
    assert len(calls) == 2 and "did not call a tool" in calls[1].messages[-1].content

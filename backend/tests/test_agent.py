import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage

from ugecy import agent as agent_module
from ugecy.tools import firecrawl as fc_tools


class ToolCallingFake(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


class FakeFirecrawl:
    def search(self, query, **kw):
        from firecrawl.v2.types import SearchData, SearchResultWeb

        return SearchData(web=[SearchResultWeb(url="https://a.test", title="A")])


def test_rejects_anthropic_and_missing_models(monkeypatch):
    monkeypatch.delenv("UGECY_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="UGECY_MODEL"):
        agent_module.resolve_model()
    with pytest.raises(ValueError, match="Anthropic"):
        agent_module.resolve_model("anthropic:claude-opus-5")


def test_agent_can_call_firecrawl_search(monkeypatch):
    monkeypatch.setattr(agent_module, "firecrawl_tools", lambda: fc_tools.firecrawl_tools(FakeFirecrawl()))
    model = ToolCallingFake(messages=iter([
        AIMessage(content="", tool_calls=[
            {"name": "firecrawl_search", "args": {"query": "ugc hooks"}, "id": "call_1"}
        ]),
        AIMessage(content="Found https://a.test"),
    ]))
    result = agent_module.build_agent(model=model).invoke({"messages": "Research UGC hooks"})
    tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert tool_msgs and tool_msgs[0].name == "firecrawl_search"
    assert "https://a.test" in tool_msgs[0].content
    assert result["messages"][-1].content == "Found https://a.test"

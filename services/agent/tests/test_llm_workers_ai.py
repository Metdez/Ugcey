import os

import pytest

from ugecy.llm.routing import ROLES, models_for
from ugecy.llm.workers_ai import ChatWorkersAI, make_model
from ugecy.settings import Settings


def test_edge_mode_uses_internal_gateway():
    m = make_model("orchestrator", Settings(internal_mode="edge", cf_api_token="secret"))
    assert m.openai_api_base == "http://llm.internal/v1"
    assert m.openai_api_key.get_secret_value() == "intercepted"


def test_local_mode_uses_cloudflare_with_account_and_token():
    m = make_model("research", Settings(internal_mode="local", cf_account_id="acct1", cf_api_token="tok"))
    assert m.openai_api_base == "https://api.cloudflare.com/client/v4/accounts/acct1/ai/v1"
    assert m.openai_api_key.get_secret_value() == "tok"
    assert m.model_name == "@cf/deepseek-ai/deepseek-v4.1-flash-1017"
    assert m.max_retries == 1 and not m.use_responses_api
    assert m.profile["max_input_tokens"] == 200_000


def test_per_model_kwargs_and_context():
    s = Settings(internal_mode="edge")
    fast = make_model("fast", s)
    assert fast.extra_body == {"chat_template_kwargs": {"enable_thinking": False}}
    assert fast.reasoning_effort is None and fast.profile["max_input_tokens"] == 131_072
    assert make_model("vision", s).profile["max_input_tokens"] == 262_144
    assert make_model("orchestrator", s).reasoning_effort == "high"


def test_routing_covers_all_roles():
    models = models_for(Settings(internal_mode="edge"))
    assert set(models) == set(ROLES) and all(isinstance(m, ChatWorkersAI) for m in models.values())
    assert not any("anthropic" in m.model_name.lower() or "claude" in m.model_name.lower() for m in models.values())


def test_payload_flattens_text_blocks_and_null_content():
    m = make_model("fast", Settings(internal_mode="edge"))
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    msgs = [SystemMessage(content=[{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]),
            HumanMessage(content="hi"), AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "1"}])]
    payload = m._get_request_payload(msgs)
    assert payload["messages"][0]["content"] == "a\n\nb"
    assert payload["messages"][2]["content"] == ""


@pytest.mark.live
async def test_live_orchestrator_turn():
    if not (os.environ.get("UGECY_LIVE") and os.environ.get("CLOUDFLARE_ACCOUNT_ID")):
        pytest.skip("set UGECY_LIVE=1 with Cloudflare credentials to run")
    s = Settings(internal_mode="local")
    out = await make_model("orchestrator", s).ainvoke("Reply with the single word: pong")
    assert "pong" in str(out.content).lower()

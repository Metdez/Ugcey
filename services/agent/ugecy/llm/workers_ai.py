"""Workers AI chat client (OpenAI-compatible) with reasoning capture and payload normalization.

Quirks and workarounds: .planning/research/MODELS.md (Q1-Q17).
"""
from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

from ugecy.settings import Settings

EDGE_BASE_URL = "http://llm.internal/v1"  # intercepted by the Worker; the real token never enters the container
CF_BASE_URL = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1"

# context window by model id; summarization triggers at 85% of it. 1M windows are capped at 200k.
CONTEXT_TOKENS: dict[str, int] = {
    "@cf/zai-org/glm-5.3": 200_000,
    "@cf/deepseek-ai/deepseek-v4.1-flash-1017": 200_000,
    "@cf/qwen/qwen3.8-27b": 262_144,
    "@cf/zai-org/glm-4.7-flash": 131_072,
}
DEFAULT_CONTEXT = 131_072

# Never reasoning_effort on glm-4.7-flash (400) and never tool_choice="required" (Q5, Q10).
MODEL_KWARGS: dict[str, dict[str, Any]] = {
    "@cf/zai-org/glm-5.3": {"reasoning_effort": "high"},
    "@cf/zai-org/glm-4.7-flash": {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}},
    "@cf/deepseek-ai/deepseek-v4.1-flash-1017": {"reasoning_effort": "high"},
    "@cf/qwen/qwen3.8-27b": {"reasoning_effort": "medium"},
}


class ChatWorkersAI(ChatOpenAI):
    """ChatOpenAI that keeps `reasoning_content`/`reasoning` and sends string-only message content."""

    def _convert_chunk_to_generation_chunk(self, chunk, default_chunk_class, base_generation_info):
        gc = super()._convert_chunk_to_generation_chunk(chunk, default_chunk_class, base_generation_info)
        choices = chunk.get("choices") or []
        if gc is not None and choices:
            delta = choices[0].get("delta") or {}
            reasoning = delta.get("reasoning_content") or delta.get("reasoning")  # some models send both
            if reasoning:
                gc.message.additional_kwargs["reasoning_content"] = reasoning
        return gc

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        for m in payload.get("messages", []):
            c = m.get("content")
            if isinstance(c, list) and c and all(isinstance(b, dict) and b.get("type") == "text" for b in c):
                m["content"] = "\n\n".join(b.get("text", "") for b in c)  # deepagents system prompt is a block list
            elif c is None:
                m["content"] = ""
        return payload

    def _create_chat_result(self, response, generation_info=None):
        res = super()._create_chat_result(response, generation_info)
        rd = response if isinstance(response, dict) else response.model_dump(warnings=False)
        for g, ch in zip(res.generations, rd.get("choices") or [], strict=False):
            msg = ch.get("message") or {}
            reasoning = msg.get("reasoning_content") or msg.get("reasoning")
            if reasoning:
                g.message.additional_kwargs["reasoning_content"] = reasoning
        return res


def make_model(role: str, settings: Settings) -> ChatWorkersAI:
    """Build the chat model for a routing role (orchestrator|research|creative|critic|fast|vision|fallback)."""
    model_id = settings.model_for(role)
    if settings.internal_mode == "edge":
        base_url, api_key = EDGE_BASE_URL, "intercepted"
    else:  # local and test: direct to Cloudflare with the developer's token (placeholders in test)
        base_url = CF_BASE_URL.format(account=settings.cf_account_id or "unset")
        api_key = settings.cf_api_token or "unset"
    kwargs: dict[str, Any] = {
        "model": model_id, "base_url": base_url, "api_key": api_key, "streaming": True, "stream_usage": True,
        "max_completion_tokens": 8192, "timeout": settings.llm_timeout_s, "max_retries": 1,
        "use_responses_api": False, "http_socket_options": (),
        "profile": {"max_input_tokens": CONTEXT_TOKENS.get(model_id, DEFAULT_CONTEXT)},
    }
    kwargs.update(MODEL_KWARGS.get(model_id, {}))
    if role == "vision" and "deepseek" in model_id:
        kwargs["reasoning_effort"] = "low"  # screen reading needs speed, not long reasoning
    return ChatWorkersAI(**kwargs)

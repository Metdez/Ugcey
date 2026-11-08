"""Screen-reading model on the OpenAI Responses API (GPT-6 Luna via Workers AI unified billing).

Same `ainvoke(messages) -> .content` surface the vision helpers use. Retries the same model once on error.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx

from ugecy.settings import Settings

EDGE_URL = "http://llm.internal/v1/responses"
CF_URL = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1/responses"


def to_responses_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for m in messages:
        content = m["content"] if isinstance(m["content"], list) else [{"type": "text", "text": m["content"]}]
        parts = []
        for c in content:
            if c["type"] == "text":
                parts.append({"type": "input_text", "text": c["text"]})
            elif c["type"] == "image_url":
                parts.append({"type": "input_image", "image_url": c["image_url"]["url"]})
        out.append({"role": m.get("role", "user"), "content": parts})
    return out


def output_text(resp: dict[str, Any]) -> str:
    if resp.get("output_text"):
        return resp["output_text"]
    return "".join(c.get("text", "") for o in resp.get("output", []) if o.get("type") == "message"
                   for c in o.get("content", []))


class ResponsesVision:
    def __init__(self, settings: Settings, model_id: str, fallback: Any = None,
                 transport: httpx.AsyncBaseTransport | None = None):
        self._s, self.model_id, self.fallback, self._transport = settings, model_id, fallback, transport

    async def ainvoke(self, messages: list[dict[str, Any]]) -> Any:
        try:
            return SimpleNamespace(content=await self._call(messages))
        except Exception:  # noqa: BLE001 any transport/model error: retry once
            if self.fallback is None:  # no other model: retry the same model once
                return SimpleNamespace(content=await self._call(messages))
            return await self.fallback.ainvoke(messages)

    async def _call(self, messages: list[dict[str, Any]]) -> str:
        edge = self._s.internal_mode == "edge"
        url = EDGE_URL if edge else CF_URL.format(account=self._s.cf_account_id or "unset")
        headers = {} if edge else {"Authorization": f"Bearer {self._s.cf_api_token or 'unset'}"}
        body = {"model": self.model_id, "input": to_responses_input(messages), "max_output_tokens": 4000}
        async with httpx.AsyncClient(timeout=self._s.llm_timeout_s, transport=self._transport) as c:
            r = await c.post(url, json=body, headers=headers)
        r.raise_for_status()
        j = r.json()
        text = output_text(j.get("result", j) if isinstance(j, dict) else {})
        if not text:
            raise ValueError("empty response from vision model")
        return text

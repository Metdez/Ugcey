"""Open-model compatibility: strip leaked <think> blocks, parse text tool calls, nudge narration.

Adapted from deepagents' Nemotron profile (DEEPAGENTS.md section 9). Runs on the model response.
"""
from __future__ import annotations

import json
import re
import uuid

from langchain.agents.middleware.types import AgentMiddleware, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage

_THINK = re.compile(r"<think\b[^>]*>.*?</think>\s*", re.DOTALL | re.IGNORECASE)
_THINK_OPEN = re.compile(r"<think\b[^>]*>.*\Z", re.DOTALL | re.IGNORECASE)  # unterminated block
_TEXT_CALL = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
_NARRATION = re.compile(
    r"\b(i['’]ll|i will|let me|i['’]m going to|next,? i(?:'ll| will))\s+(?:now\s+)?"
    r"(call|use|run|invoke|delegate|write|search|fetch|start|create|check|generate)\b", re.IGNORECASE)
NUDGE = ("You described a next step but did not call a tool. Do it now by calling the tool, "
         "or reply with the final answer if the plan is complete.")


def strip_think(text: str) -> str:
    return _THINK_OPEN.sub("", _THINK.sub("", text)).strip()


def parse_text_tool_calls(text: str, known: set[str] | None = None) -> tuple[str, list[dict]]:
    """Extract <tool_call>{"name":..,"arguments":{..}}</tool_call> blocks; returns (remaining text, tool_calls)."""
    calls: list[dict] = []
    for raw in _TEXT_CALL.findall(text):
        try:
            obj = json.loads(raw)
            name = obj["name"]
            args = obj.get("arguments", obj.get("args", {}))
            args = json.loads(args) if isinstance(args, str) else args
        except (ValueError, KeyError, TypeError):
            continue
        if isinstance(args, dict) and (known is None or name in known):
            calls.append({"name": name, "args": args, "id": f"call_{uuid.uuid4().hex[:12]}", "type": "tool_call"})
    return _TEXT_CALL.sub("", text).strip(), calls


def _clean(msg: AIMessage, known: set[str]) -> AIMessage:
    text = msg.content if isinstance(msg.content, str) else None
    if text is None:  # block-list content: leave untouched
        return msg
    text = strip_think(text)
    calls = list(msg.tool_calls)
    if not calls and "<tool_call>" in text:
        text, calls = parse_text_tool_calls(text, known)
    if text == msg.content and calls == list(msg.tool_calls):
        return msg
    return msg.model_copy(update={"content": text, "tool_calls": calls})


def _first_ai(response: ModelResponse) -> AIMessage | None:
    return next((m for m in response.result if isinstance(m, AIMessage)), None)


class CompatMiddleware(AgentMiddleware):
    name = "CompatMiddleware"

    def __init__(self, nudge: bool = True) -> None:
        self.nudge = nudge

    def _fix(self, response: ModelResponse, known: set[str]) -> ModelResponse:
        response.result = [_clean(m, known) if isinstance(m, AIMessage) else m for m in response.result]
        return response

    async def awrap_model_call(self, request, handler):
        known = {getattr(t, "name", None) for t in request.tools} - {None}
        response = self._fix(await handler(request), known)
        ai = _first_ai(response)
        if (self.nudge and known and ai is not None and not ai.tool_calls and isinstance(ai.content, str)
                and _NARRATION.search(ai.content[-400:])):
            retry = request.override(messages=[*request.messages, ai, HumanMessage(content=NUDGE)])
            response = self._fix(await handler(retry), known)  # one nudge only
        return response

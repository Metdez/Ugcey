"""Stuck recovery: when an agent loops, tell it to look the situation up with Firecrawl (web_search / fetch_page).

Never a blocker (AGENTS.md rule 8). Nothing is capped, stopped or denied. The nudge is appended to the system
message of the next model call only, never written to state. A web lookup resets the window, so the agent is
nudged again only if it gets stuck again after searching.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from deepagents.middleware._utils import append_to_system_message
from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import AIMessage, ToolMessage

from ugecy.memory import experience

LOOKUP_TOOLS = {"web_search", "fetch_page", "tavily_search", "tavily_extract", "tavily_research"}
POLLING_TOOLS = {"check_media_job", "get_post_status"}  # repeating these with the same result is normal waiting
SCREEN_TOOLS = {"device_screenshot", "device_observe"}
REPEAT, ERRORS, SAME = 3, 3, 3


@dataclass(frozen=True)
class Stuck:
    kind: str  # repeat | errors | no_change
    tool: str
    detail: str
    query: str

    @property
    def note(self) -> str:
        return f"{self.kind}: {self.detail}"


def _text(m: Any) -> str:
    c = getattr(m, "content", "")
    return c if isinstance(c, str) else " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in c)


def _is_error(m: ToolMessage) -> bool:
    t = _text(m).lstrip().lower()
    return getattr(m, "status", None) == "error" or t.startswith(("error", '{"error"'))


def _screen(text: str) -> tuple[str, frozenset[str]] | None:
    """(app, element labels) of a device_screenshot/observe result, used to tell that the screen did not change."""
    try:
        d = json.loads(text[: text.rfind("}") + 1] or "{}")
    except ValueError:
        return None
    if not isinstance(d, dict) or "elements" not in d:
        return None
    labels = frozenset(str(e.get("label", "")).lower() for e in d.get("elements") or [] if isinstance(e, dict))
    return str(d.get("app", "")).lower(), labels


def _same_screen(a: tuple[str, frozenset[str]], b: tuple[str, frozenset[str]]) -> bool:
    if a[0] != b[0]:
        return False
    union = a[1] | b[1]
    return not union or len(a[1] & b[1]) / len(union) >= 0.8


def _norm(text: str) -> str:
    return re.sub(r'"?steps_used"?\s*[:=]\s*\d+', "", text).strip()[:2000]


def _window(messages: list[Any]) -> list[Any]:
    """Messages after the most recent web lookup (a lookup means the agent already took the advice)."""
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if isinstance(m, AIMessage) and any(tc.get("name") in LOOKUP_TOOLS for tc in m.tool_calls or []):
            return messages[i + 1:]
    return messages


def _query(tool: str, err: str = "", screen: str = "") -> str:
    hint = re.sub(r"\s+", " ", re.sub(r"[{}\"\[\]]", " ", err)).strip()[:120]
    if tool.startswith("device_"):
        return f"iPhone {screen or 'iOS'} how to {hint or 'get past this screen'}".strip()
    return f"{tool.replace('_', ' ')} {hint}".strip() or tool


def detect(messages: list[Any]) -> Stuck | None:
    """Pure check over the conversation so far. Returns the stuck pattern, or None."""
    win = _window(messages)
    calls: list[tuple[str, str, str]] = []  # (id, name, args)
    for m in win:
        if isinstance(m, AIMessage):
            calls += [(tc.get("id") or "", tc["name"], json.dumps(tc.get("args") or {}, sort_keys=True, default=str))
                      for tc in m.tool_calls or [] if tc["name"] not in LOOKUP_TOOLS]
    results = {m.tool_call_id: m for m in win if isinstance(m, ToolMessage)}
    done = [(name, args, results[cid]) for cid, name, args in calls if cid in results]
    if not done:
        return None
    # 1. N tool errors in a row
    tail = done[-ERRORS:]
    if len(tail) == ERRORS and all(_is_error(r) for _, _, r in tail):
        name, _, last = tail[-1]
        err = _text(last)[:300]
        return Stuck("errors", name, f"the last {ERRORS} tool calls failed (latest {name}: {err[:160]})", _query(name, err))
    # 2. acting on the phone but the screen does not change
    screens = [(s, a) for nm, a, r in done if nm in SCREEN_TOOLS and not _is_error(r) and (s := _screen(_text(r)))]
    acted = any(nm.startswith("device_") and nm not in SCREEN_TOOLS for nm, _, _ in done)
    if acted and len(screens) >= SAME and all(_same_screen(screens[-1][0], s) for s, _ in screens[-SAME:]):
        app = screens[-1][0][0] or "the current app"
        return Stuck("no_change", "device", f"the phone screen ({app}) has not changed across the last {SAME} looks "
                     "even though you acted on it", _query("device_", screen=app))
    # 3. the same call repeated with the same result
    for (name, args), n in Counter((nm, a) for nm, a, _ in done).most_common(3):
        if n < REPEAT or name in POLLING_TOOLS:
            break
        outs = [_norm(_text(r)) for nm, a, r in done if (nm, a) == (name, args)][-REPEAT:]
        if len(set(outs)) == 1:
            err = outs[0] if outs[0].lower().startswith(("error", '{"error"')) else ""
            return Stuck("repeat", name, f"called {name} with the same arguments {n} times and got the same result",
                         _query(name, err))
    return None


def nudge(s: Stuck, has_lookup: bool) -> str:
    how = (f'Call `web_search` now (suggested query: "{s.query}"), read the best result with `fetch_page` if '
           "needed, and work out why this is happening")
    if not has_lookup:
        how = (f'Delegate a quick lookup to research-analyst (web_search, suggested query: "{s.query}") '
               "or try a different specialist")
    return (f"<stuck_recovery>\nYou appear stuck: {s.detail}.\n{how}. Then change your approach: do not repeat the "
            "same action again. If what you learn is a reusable how-to, save it to your memory file with `edit_file`."
            "\n</stuck_recovery>")


class StuckMiddleware(AgentMiddleware):
    name = "StuckMiddleware"

    def __init__(self, has_lookup: bool = True) -> None:
        super().__init__()
        self.has_lookup = has_lookup

    async def awrap_model_call(self, request, handler):
        try:
            s = detect(list(request.messages or []))
        except Exception:  # noqa: BLE001 - detection must never break a model call
            s = None
        if s is None:
            return await handler(request)
        experience.note_stuck(s.note)
        return await handler(request.override(system_message=append_to_system_message(
            request.system_message, nudge(s, self.has_lookup))))

"""Continuous agent memory, recorded automatically after every subagent task and orchestrator turn.

- Episodic: /memories/episodes/<agent>.md holds dated run records (task, tools, errors, stuck events, result).
- Semantic: /memories/agents/<agent>.md holds the lessons list. The fast model merges each new episode into it,
  and LiveMemoryMiddleware loads it into that agent's system prompt on its next run.

Recording runs in the background and never delays or fails a run.
"""
from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from deepagents.backends.utils import create_file_data
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from ugecy.interfaces import memories_ns

log = logging.getLogger(__name__)
KEEP_EPISODES = 60  # file housekeeping so the Memory tab stays readable; not a run limit
KEEP_LESSONS = 25
EPISODE_SEP = "\n\n---\n\n"
_TASKS: set[asyncio.Task] = set()
_LOCKS: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_STUCK: dict[tuple[str, str], list[str]] = defaultdict(list)

LESSONS_PROMPT = """You maintain the long-term memory of the "{agent}" agent in a UGC content workspace \
(research, scripts, Higgsfield media, a real iPhone driven through Glasshand, publishing to the operator's own accounts).
Update the agent's lessons from the new run record. Lessons are short, specific, reusable how-tos:
- what worked (exact navigation paths, tool argument patterns, sources that had good data);
- what failed and the fix that worked (or what to try next time);
- tool and app quirks, and operator preferences shown in the task.
Keep useful old lessons, merge duplicates, rewrite ones the new evidence corrects, drop ones it disproves.
At most {keep} bullets, each one line under 200 characters, most useful first.
Never write passwords, verification codes, API keys, tokens, email addresses, phone numbers or other personal data.
If the run taught nothing new, return the current lessons unchanged.
Output only the bullet list, one "- " line per lesson, no headings or commentary."""


def _key() -> tuple[str, str]:
    try:
        from langgraph.config import get_config

        cfg = get_config()
        return ((cfg.get("configurable") or {}).get("thread_id") or "",
                (cfg.get("metadata") or {}).get("lc_subagent_tool_call_id") or "main")
    except Exception:  # noqa: BLE001 - outside a run
        return "", "main"


def note_stuck(note: str) -> None:
    notes = _STUCK[_key()]
    if note not in notes:
        notes.append(note)


def take_stuck() -> list[str]:
    return _STUCK.pop(_key(), [])


def _text(m: Any) -> str:
    t = getattr(m, "text", None)
    if isinstance(t, str):
        return t
    c = getattr(m, "content", "")
    return c if isinstance(c, str) else " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in c)


def _one_line(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def episode_from(messages: list[Any], agent: str, stuck: list[str] | None = None) -> dict[str, Any] | None:
    """Summarize the latest run in `messages`: everything after the last human message."""
    start = next((i for i in range(len(messages) - 1, -1, -1) if isinstance(messages[i], HumanMessage)), None)
    if start is None:
        return None
    run = messages[start:]
    names = {tc.get("id"): tc["name"] for m in run if isinstance(m, AIMessage) for tc in m.tool_calls or []}
    used: Counter[str] = Counter(names.values())
    failed: Counter[str] = Counter()
    errors: list[str] = []
    for m in run:
        if isinstance(m, ToolMessage):
            t = _text(m)
            if getattr(m, "status", None) == "error" or t.lstrip().lower().startswith(("error", '{"error"')):
                name = names.get(m.tool_call_id, m.name or "tool")
                failed[name] += 1
                errors.append(f"{name}: {_one_line(t, 180)}")
    final = next((_text(m) for m in reversed(run) if isinstance(m, AIMessage) and not m.tool_calls and _text(m).strip()), "")
    outcome = "stopped" if final.startswith("Stopped by the operator") else "errors" if failed else "ok"
    return {"agent": agent, "at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"), "outcome": outcome,
            "task": _one_line(_text(run[0]), 500), "tools": dict(used), "failed": dict(failed),
            "errors": errors[-6:], "stuck": list(stuck or []), "result": _one_line(final, 700)}


def episode_md(e: dict[str, Any]) -> str:
    tools = ", ".join(f"{n}×{c}" + (f" ({e['failed'][n]} failed)" if e["failed"].get(n) else "")
                      for n, c in sorted(e["tools"].items(), key=lambda kv: -kv[1])) or "none"
    lines = [f"## {e['at']} · {e['outcome']}", f"Task: {e['task']}", f"Tools: {tools}"]
    lines += [f"Error: {x}" for x in e["errors"]]
    lines += [f"Stuck: {x}" for x in e["stuck"]]
    lines.append(f"Result: {e['result'] or '(no final message)'}")
    return "\n".join(lines)


def _bullets(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip().startswith("- ") and len(ln.strip()) > 3]


def lessons_doc(agent: str, bullets: list[str]) -> str:
    return (f"# {agent} lessons\n\nLearned automatically from past runs (episodes in /memories/episodes/{agent}.md). "
            "Agents and the operator can edit this file; the newest evidence wins.\n\n" + "\n".join(bullets) + "\n")


async def _read(store: Any, ns: tuple[str, ...], key: str) -> tuple[str, str | None]:
    item = await store.aget(ns, key)
    if item is None:
        return "", None
    v = item.value
    c = v.get("content", "")
    return ("\n".join(c) if isinstance(c, list) else str(c)), v.get("created_at")


async def _write(store: Any, ns: tuple[str, ...], key: str, text: str, created: str | None) -> None:
    await store.aput(ns, key, create_file_data(text, created_at=created))


async def merge_lessons(model: Any, agent: str, current: list[str], episode: str) -> list[str]:
    msg = await model.ainvoke([
        SystemMessage(content=LESSONS_PROMPT.format(agent=agent, keep=KEEP_LESSONS)),
        HumanMessage(content=f"Current lessons:\n{chr(10).join(current) or '(none yet)'}\n\nNew run record:\n{episode}"),
    ])
    out = [_one_line(b, 240) for b in _bullets(_text(msg))][:KEEP_LESSONS]
    return out or current


async def record(store: Any, workspace_id: str, episode: dict[str, Any], model: Any | None) -> None:
    agent, ns, md = episode["agent"], memories_ns(workspace_id), episode_md(episode)
    ep_key, ls_key = f"/episodes/{agent}.md", f"/agents/{agent}.md"
    async with _LOCKS[f"{workspace_id}:{ep_key}"]:
        old, created = await _read(store, ns, ep_key)
        entries = [x for x in old.split(EPISODE_SEP) if x.strip().startswith("## ")] if old else []
        entries = (entries + [md])[-KEEP_EPISODES:]
        header = f"# {agent} episodes\n\nOne record per run, newest last."
        await _write(store, ns, ep_key, EPISODE_SEP.join([header, *entries]) + "\n", created)
    if model is None or (not episode["tools"] and not episode["stuck"]):
        return  # nothing was done, so there is nothing to learn
    async with _LOCKS[f"{workspace_id}:{ls_key}"]:
        old, created = await _read(store, ns, ls_key)
        current = _bullets(old)
        try:
            merged = await merge_lessons(model, agent, current, md)
        except Exception:
            log.warning("lesson merge failed for %s", agent, exc_info=True)
            return
        if merged and merged != current:
            await _write(store, ns, ls_key, lessons_doc(agent, merged), created)


def schedule(store: Any, workspace_id: str, episode: dict[str, Any], model: Any | None) -> None:
    async def _run() -> None:
        try:
            await record(store, workspace_id, episode, model)
        except Exception:
            log.warning("memory record failed for %s", episode.get("agent"), exc_info=True)

    task = asyncio.get_running_loop().create_task(_run())
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)


async def drain() -> None:
    """Wait for pending memory writes (tests and shutdown)."""
    while _TASKS:
        await asyncio.gather(*list(_TASKS), return_exceptions=True)

"""Domain device tools. Input tools are guarded in code (approved session + step budget), not just by prompt."""
from __future__ import annotations

import json
from typing import Literal
from uuid import uuid4

from langchain_core.tools import tool

from ugecy.contracts import AuditEntry, DeviceSessionInfo, DeviceStatus, Source
from ugecy.deps import get_deps
from ugecy.events import current_thread_id, emit
from ugecy.integrations.unavailable import DEVICE_OFF, NotConnected
from ugecy.registry import register_tool

# shortcut: session state is module-level memory (single operator, single process); persist it in KV when multi-worker
_STATE: dict = {"session": None, "last_action": None, "control": "idle", "allowed_apps": [], "purpose": "operate", "observed": 0}
RESEARCH_STEPS, RESEARCH_POSTS, RESEARCH_TYPE_MAX = 60, 12, 80
HINT = ("\nHow to act: pass an element's x,y (0..1, centre) to device_tap; re-describe after every action. "
        "If your target is not in elements, use device_scroll (more_below=true means the list continues) or device_back; "
        "tap the text field first, then re-describe before typing. "
        "If the screen did not change after an action, change strategy instead of repeating it. "
        "On control_taken stop; never replay after an ambiguous failure.")
INTENTS = {"post", "send", "purchase", "delete", "login", "signup", "confirm"}


def reset_state() -> None:
    _STATE.update(session=None, last_action=None, control="idle", allowed_apps=[], purpose="operate", observed=0)


async def _audit(tool_name: str, status: str, detail: str) -> None:
    d = get_deps()
    await d.app.add_audit(AuditEntry(id=uuid4().hex, thread_id=current_thread_id(), actor="agent", action="device_action",
                                     tool=tool_name, status=status, mode=d.device.mode, detail=detail[:500]))  # type: ignore[arg-type]


async def device_status_snapshot() -> DeviceStatus:
    d = get_deps()
    try:
        devices = await d.device.list_devices()
    except Exception:  # noqa: BLE001
        devices = []
    return DeviceStatus(provider=d.device.name, mode=d.device.mode, devices=devices, session=_STATE["session"],
                        control=_STATE["control"], last_action=_STATE["last_action"])


async def _act(tool_name: str, action: dict, detail: str) -> str:
    s: DeviceSessionInfo | None = _STATE["session"]
    if s is None:
        return "error: no active approved device session; call device_start_session first"
    if _STATE["control"] == "human":
        return "error: a human has taken control of the device; stop and wait"
    if s.steps_used >= s.max_steps:
        return f"error: step budget exhausted ({s.max_steps}); start a new session"
    d = get_deps()
    _STATE["session"] = s.model_copy(update={"steps_used": s.steps_used + 1})
    try:
        r = await d.device.send(s.device_id, action, idempotency_key=uuid4().hex)
    except NotConnected as e:
        return f"error: {e}"
    except Exception as e:  # noqa: BLE001
        await _audit(tool_name, "error", f"{detail}: {type(e).__name__}")
        return f"error: device send failed ({type(e).__name__}); take a screenshot before retrying, never blindly replay"
    _STATE["last_action"] = f"{detail}: {'ok' if r['ok'] else r['error']}"
    if (r.get("error_code") or r.get("error")) == "control_taken":
        _STATE["control"] = "human"
    await _audit(tool_name, "ok" if r["ok"] else "error", _STATE["last_action"])
    return json.dumps({**r, "steps_left": s.max_steps - s.steps_used - 1})


@tool
async def device_status() -> str:
    """Show device provider mode, available devices, the active session and last action."""
    return (await device_status_snapshot()).model_dump_json()


@tool
async def device_screenshot() -> str:
    """Describe the device screen: JSON with app, screen and elements (label, kind, normalized x,y). Call before and after every action."""
    d = get_deps()
    devices = await d.device.list_devices()
    if not devices:
        return f"error: {DEVICE_OFF}"
    try:
        text = await d.device.describe(devices[0].id)
    except NotConnected as e:
        return f"error: {e}"
    except Exception as e:  # noqa: BLE001
        return f"error: screen capture/vision failed ({type(e).__name__}); retry device_screenshot"
    _STATE["last_action"] = "screenshot"
    await _audit("device_screenshot", "ok", text[:200])
    return text + HINT


@tool
async def device_observe(note: str = "") -> str:
    """Read the short-form post on screen and record it as a source: creator, caption, on-screen text, hook_guess, metrics (numbers),
    audio, format_guess, is_ad and elements with x,y. Call once per post after it has played; `note` is optional context. No session needed."""
    d = get_deps()
    devices = await d.device.list_devices()
    if not devices:
        return f"error: {DEVICE_OFF}"
    if _STATE["purpose"] == "research" and _STATE["session"] is not None and _STATE["observed"] >= RESEARCH_POSTS:
        return f"error: post limit reached ({RESEARCH_POSTS} per research session); write your pattern cards"
    try:
        post = await getattr(d.device, "observe")(devices[0].id)  # noqa: B009
    except NotConnected as e:
        return f"error: {e}"
    except Exception as e:  # noqa: BLE001
        return f"error: observe failed ({type(e).__name__}); retry or use device_screenshot"
    if post is None or post.get("error") or not (post.get("creator") or post.get("caption") or post.get("hook_guess")):
        return json.dumps({"error": post.get("error") if post else "observe unavailable", "hint": "no post is on screen; open one, then observe again",
                           "elements": (post or {}).get("elements", [])})
    handle = post["creator"].lstrip("@") or "unknown"
    plat = post["platform"] if post["platform"] != "other" else "tiktok"
    url = post["url"] if post.get("url", "").startswith("http") else f"device://{plat}/{handle}"
    m = post["metrics"]
    snippet = f"hook: {post['hook_guess']} | " + ", ".join(f"{k} {v}" for k, v in m.items()) + (f" | note: {note}" if note else "")
    src = Source(url=url, title=f"{plat} post by @{handle}", platform=plat if plat in ("tiktok", "instagram", "youtube", "facebook") else None,
                 snippet=snippet[:500])
    emit("source.added", source=src.model_dump())
    if tid := current_thread_id():
        await d.app.add_source(tid, src)
    _STATE["observed"] += 1
    _STATE["last_action"] = f"observed {url}"
    await _audit("device_observe", "ok", f"{url} {d.device.mode}")
    return json.dumps({**post, "source_url": url, "mode": d.device.mode, "observed": _STATE["observed"],
                       **({"note": note} if note else {})}, separators=(",", ":"), ensure_ascii=False)


@tool
async def device_start_session(goal: str, allowed_apps: list[str] | None = None, max_steps: int = 60,
                               purpose: Literal["research", "operate"] = "operate") -> str:
    """Start a bounded device-control session for a goal (needs operator approval). Required before tap/swipe/type.

    `allowed_apps` optionally records operating scope. purpose="research" is read-only browsing of short-form apps:
    60 steps, search queries up to 80 chars, device_commit refused."""
    d = get_deps()
    devices = await d.device.list_devices()
    if not devices:
        return f"error: {DEVICE_OFF}"
    sess = DeviceSessionInfo(id=uuid4().hex[:12], device_id=devices[0].id, goal=goal, steps_used=0, max_steps=RESEARCH_STEPS if purpose == "research" else max(1, min(max_steps, 200)))
    apps = list(allowed_apps or [])
    _STATE.update(session=sess, control="agent", allowed_apps=apps, last_action="session started", purpose=purpose, observed=0)
    await _audit("device_start_session", "ok", f"goal={goal!r} apps={apps} purpose={purpose} max_steps={sess.max_steps}")
    return sess.model_dump_json()


@tool
async def device_tap(x: float, y: float) -> str:
    """Tap at normalized coordinates (0..1). Needs an active approved session."""
    return await _act("device_tap", {"type": "tap", "x": x, "y": y}, f"tap ({x:.2f},{y:.2f})")


@tool
async def device_swipe(from_x: float, from_y: float, to_x: float, to_y: float) -> str:
    """Swipe between normalized points. Needs an active approved session."""
    return await _act("device_swipe", {"type": "swipe", "from_x": from_x, "from_y": from_y, "to_x": to_x, "to_y": to_y}, "swipe")


@tool
async def device_next_post() -> str:
    """In a short-form feed, swipe up to the next post. Needs an active approved session."""
    return await _act("device_next_post", {"type": "swipe", "from_x": 0.5, "from_y": 0.8, "to_x": 0.5, "to_y": 0.25}, "next post")


@tool
async def device_scroll(direction: str = "down") -> str:
    """Scroll the current list or page: "down" reveals content further down, "up" goes back toward the top. Needs a session."""
    if direction not in ("down", "up"):
        return 'error: direction must be "down" or "up"'
    a, b = (0.72, 0.32) if direction == "down" else (0.32, 0.72)
    return await _act("device_scroll", {"type": "swipe", "from_x": 0.5, "from_y": a, "to_x": 0.5, "to_y": b}, f"scroll {direction}")


@tool
async def device_back() -> str:
    """Go back one screen (iOS edge swipe from the left). Needs an active approved session."""
    return await _act("device_back", {"type": "swipe", "from_x": 0.02, "from_y": 0.5, "to_x": 0.75, "to_y": 0.5}, "back")


@tool
async def device_open_url(url: str) -> str:
    """Open a public https URL in Safari on the iPhone (Home, Spotlight, type the URL, Enter). Use it to bring an
    approved Higgsfield asset URL onto the phone so it can be saved to Photos and posted. Needs a session (3 steps)."""
    if not url.startswith("https://") or len(url) > 500 or not url.isascii() or any(c.isspace() for c in url):
        return "error: url must be an ASCII https URL without spaces, at most 500 characters"
    if _STATE["purpose"] == "research":
        return "error: device_open_url is for operate sessions (publishing), not research"
    for tool_name, action, detail in (
        ("device_home", {"type": "home"}, "home"),
        ("device_swipe", {"type": "swipe", "from_x": 0.5, "from_y": 0.35, "to_x": 0.5, "to_y": 0.75}, "spotlight"),
        ("device_type", {"type": "type", "text": url + "\n"}, f"open url ({len(url)} chars)"),
    ):
        out = await _act(tool_name, action, detail)
        if out.startswith("error"):
            return out
    return "ok: URL submitted in Spotlight; call device_screenshot to confirm Safari opened it"


@tool
async def device_type(text: str) -> str:
    """Type printable ASCII text (max 512 chars; in a research session max 80, a search query only). Needs an active approved session."""
    if _STATE["purpose"] == "research" and len(text) > RESEARCH_TYPE_MAX:
        return f"error: research sessions may only type search queries up to {RESEARCH_TYPE_MAX} characters"
    return await _act("device_type", {"type": "type", "text": text}, f"type {len(text)} chars")


@tool
async def device_home() -> str:
    """Press Home. Needs an active approved session."""
    return await _act("device_home", {"type": "home"}, "home")


@tool
async def device_commit(intent: str, x: float, y: float) -> str:
    """Final irreversible tap (intent: post, send, purchase, delete, login, signup or confirm) at normalized x,y. Always needs approval."""
    if _STATE["purpose"] == "research" and _STATE["session"] is not None:
        return "error: device_commit is refused in a research session (read-only: no like, follow, comment, post or purchase)"
    if intent not in INTENTS:
        return f"error: intent must be one of {sorted(INTENTS)}"
    out = await _act("device_commit", {"type": "tap", "x": x, "y": y}, f"COMMIT {intent} ({x:.2f},{y:.2f})")
    return out


register_tool(device_status, domain="device")
register_tool(device_open_url, domain="device", side_effect=True)
register_tool(device_scroll, domain="device")
register_tool(device_back, domain="device")
register_tool(device_screenshot, domain="device")
register_tool(device_observe, domain="device")
register_tool(device_start_session, domain="device")  # no approval: only paid generation asks the operator
for _t in (device_tap, device_swipe, device_next_post, device_type, device_home):
    register_tool(_t, domain="device", side_effect=True)
register_tool(device_commit, domain="device", side_effect=True)

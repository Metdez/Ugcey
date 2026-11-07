"""Domain device tools. Input tools are guarded in code (approved session + step budget), not just by prompt."""
from __future__ import annotations

import json
from uuid import uuid4

from langchain_core.tools import tool

from ugecy.contracts import AuditEntry, DeviceSessionInfo, DeviceStatus
from ugecy.deps import get_deps
from ugecy.events import current_thread_id
from ugecy.registry import APPROVE_REJECT, register_tool

# shortcut: session state is module-level memory (single operator, single process); persist it in KV when multi-worker
_STATE: dict = {"session": None, "last_action": None, "control": "idle", "allowed_apps": []}
HINT = ("\nHow to act: pass an element's x,y (0..1, centre) to device_tap; re-describe after every action; "
        "on control_taken stop; never replay after an ambiguous failure.")
INTENTS = {"post", "send", "purchase", "delete"}


def reset_state() -> None:
    _STATE.update(session=None, last_action=None, control="idle", allowed_apps=[])


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
        return "error: no ready device"
    try:
        text = await d.device.describe(devices[0].id)
    except Exception as e:  # noqa: BLE001
        return f"error: screen capture/vision failed ({type(e).__name__}); retry device_screenshot"
    _STATE["last_action"] = "screenshot"
    await _audit("device_screenshot", "ok", text[:200])
    return text + HINT


@tool
async def device_start_session(goal: str, allowed_apps: list[str], max_steps: int = 25) -> str:
    """Start a bounded device-control session for a goal (needs operator approval). Required before tap/swipe/type."""
    d = get_deps()
    devices = await d.device.list_devices()
    if not devices:
        return "error: no ready device"
    sess = DeviceSessionInfo(id=uuid4().hex[:12], device_id=devices[0].id, goal=goal, steps_used=0, max_steps=max(1, min(max_steps, 100)))
    _STATE.update(session=sess, control="agent", allowed_apps=list(allowed_apps), last_action="session started")
    await _audit("device_start_session", "ok", f"goal={goal!r} apps={allowed_apps} max_steps={sess.max_steps}")
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
async def device_type(text: str) -> str:
    """Type printable ASCII text (max 512 chars). Needs an active approved session."""
    return await _act("device_type", {"type": "type", "text": text}, f"type {len(text)} chars")


@tool
async def device_home() -> str:
    """Press Home. Needs an active approved session."""
    return await _act("device_home", {"type": "home"}, "home")


@tool
async def device_commit(intent: str, x: float, y: float) -> str:
    """Final irreversible tap (intent: post, send, purchase or delete) at normalized x,y. Always needs approval."""
    if intent not in INTENTS:
        return f"error: intent must be one of {sorted(INTENTS)}"
    out = await _act("device_commit", {"type": "tap", "x": x, "y": y}, f"COMMIT {intent} ({x:.2f},{y:.2f})")
    return out


register_tool(device_status, domain="device")
register_tool(device_screenshot, domain="device")
register_tool(device_start_session, domain="device", interrupt=APPROVE_REJECT)
for _t in (device_tap, device_swipe, device_type, device_home):
    register_tool(_t, domain="device", side_effect=True)
register_tool(device_commit, domain="device", interrupt=APPROVE_REJECT, side_effect=True)

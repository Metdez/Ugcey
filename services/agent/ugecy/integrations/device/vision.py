"""Vision grounding for the live iPhone: crop/downscale a screenshot, ask the vision model, return compact JSON."""
from __future__ import annotations

import base64
import io
import json
import math
import re
from typing import Any

from PIL import Image

MAX_H = 900
KINDS = {"button", "field", "tab", "icon", "text"}
PROMPT = (
    "You see a real iPhone screen. Reply with ONLY compact JSON: "
    '{"app": "<foreground app or Home Screen>", "screen": "<one-line description>", '
    '"elements": [{"label": "<text or name>", "kind": "button|field|tab|icon|text", "x": 0.5, "y": 0.9}]}. '
    "x and y are each element's CENTRE as fractions 0..1 of the image (x from the left, y from the top). "
    "List at most 25 tappable or relevant elements, no commentary. "
    "iOS notes: this may be the Home Screen; to open an app press Home, swipe down from mid-screen to open Spotlight, then type the app name; "
    "an AssistiveTouch floating button may cover targets."
)


def crop_viewport(img: Image.Image, geometry: dict[str, Any]) -> Image.Image:
    """Crop to geometry.viewport (pixels of geometry.width x height), scaling if the image size differs."""
    vp = geometry["viewport"]
    sx, sy = img.width / (geometry.get("width") or img.width), img.height / (geometry.get("height") or img.height)
    box = (round(vp["x"] * sx), round(vp["y"] * sy), round((vp["x"] + vp["width"]) * sx), round((vp["y"] + vp["height"]) * sy))
    box = (max(0, box[0]), max(0, box[1]), min(img.width, box[2]), min(img.height, box[3]))
    if box[2] <= box[0] or box[3] <= box[1]:
        return img
    return img.crop(box)


def to_jpeg(img: Image.Image, *, max_h: int | None = None, quality: int = 85) -> bytes:
    img = img.convert("RGB")
    if max_h and img.height > max_h:
        img = img.resize((max(1, round(img.width * max_h / img.height)), max_h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def extract_json(text: str) -> dict[str, Any] | None:
    """First JSON object in model output; tolerates prose, <think> blocks and code fences."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    dec = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = dec.raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return min(1.0, max(0.0, f)) if not math.isnan(f) else None


def normalize(text: str) -> str:
    obj = extract_json(text)
    if obj is None:
        return json.dumps({"app": "", "screen": text.strip()[:200], "elements": [], "note": "model output was not JSON"}, separators=(",", ":"))
    els = []
    for e in obj.get("elements") or []:
        if not isinstance(e, dict) or (x := _num(e.get("x"))) is None or (y := _num(e.get("y"))) is None:
            continue
        kind = str(e.get("kind", "text")).lower()
        els.append({"label": str(e.get("label", ""))[:60], "kind": kind if kind in KINDS else "text", "x": round(x, 3), "y": round(y, 3)})
    out = {"app": str(obj.get("app", ""))[:60], "screen": str(obj.get("screen", ""))[:200], "elements": els[:40]}
    return json.dumps(out, separators=(",", ":"), ensure_ascii=False)


def _text(content: Any) -> str:
    if isinstance(content, list):
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return str(content or "")


async def describe_jpeg(model: Any, cropped_jpeg: bytes) -> str:
    small = to_jpeg(Image.open(io.BytesIO(cropped_jpeg)), max_h=MAX_H, quality=80)
    uri = "data:image/jpeg;base64," + base64.b64encode(small).decode()
    msg = {"role": "user", "content": [{"type": "text", "text": PROMPT}, {"type": "image_url", "image_url": {"url": uri}}]}
    resp = await model.ainvoke([msg])
    return normalize(_text(resp.content).strip())

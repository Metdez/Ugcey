"""Mock iPhone: a small screen graph rendered with Pillow (750x1334), hit-tested by normalized taps.

Home -> Photos -> Upload -> Caption -> Posted, plus a Safari handoff page. Thread-safe state.
"""
from __future__ import annotations

import io
import threading
import time
from typing import Any
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont

from tests._doubles import device_feed as feed
from ugecy.contracts import DeviceInfo
from ugecy.settings import Settings

W, H = 750, 1334
DEVICE_ID = "iphone-mock-1"
# hotspot = (label, (x0, y0, x1, y1) normalized, target screen | None); target None = text field / no-op
SCREENS: dict[str, dict[str, Any]] = {
    "home": {"title": "Home", "spots": [("Photos", (0.08, 0.10, 0.40, 0.22), "photos"), ("TikTok", (0.42, 0.10, 0.74, 0.22), "upload"),
                                        ("Safari", (0.08, 0.26, 0.40, 0.38), "safari")]},
    "photos": {"title": "Photos", "spots": [("Back", (0.03, 0.03, 0.25, 0.08), "home"), ("video_001.mp4", (0.05, 0.14, 0.48, 0.40), "upload")]},
    "upload": {"title": "TikTok - Upload", "spots": [("Back", (0.03, 0.03, 0.25, 0.08), "home"), ("Select video", (0.10, 0.20, 0.90, 0.50), None),
                                                    ("Next", (0.60, 0.88, 0.95, 0.95), "caption")]},
    "caption": {"title": "TikTok - Caption", "spots": [("Back", (0.03, 0.03, 0.25, 0.08), "upload"), ("Caption field", (0.08, 0.15, 0.92, 0.35), None),
                                                       ("Post", (0.60, 0.88, 0.95, 0.95), "posted")]},
    "posted": {"title": "Posted", "spots": [("Done", (0.30, 0.80, 0.70, 0.88), "home")]},
    "safari": {"title": "Safari - app.glasshand.com", "spots": [("Home", (0.03, 0.03, 0.25, 0.08), "home")],
               "note": "Human handoff page: take over the device here."},
}
FEED = {"spotlight", "tt_search", "tt_results", "tt_post"}
_ASCII_OK = set(map(chr, range(32, 127))) | {"\n", "\t"}


def _font(size: int) -> ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


class MockDeviceProvider:
    name = "mock-iphone"
    mode = "mock"

    def __init__(self, settings: Settings | None = None):
        self._lock = threading.Lock()
        self._screen, self._caption, self._last = "home", "", "none"
        self._query, self._post = "", 0
        self._receipts: dict[str, dict[str, Any]] = {}

    async def list_devices(self) -> list[DeviceInfo]:
        return [DeviceInfo(id=DEVICE_ID, name="Mock iPhone SE", kind="iphone", status="active", ready=True)]

    def _spots(self) -> list[tuple[str, tuple[float, float, float, float], str | None]]:
        return feed.spots(self._screen, self._query) if self._screen in FEED else SCREENS[self._screen]["spots"]

    def _title(self) -> str:
        return feed.title(self._screen, self._query, self._post) if self._screen in FEED else SCREENS[self._screen]["title"]

    def _els(self) -> list[dict[str, Any]]:
        return [{"label": n, "kind": "button", "x": round((r[0] + r[2]) / 2, 3), "y": round((r[1] + r[3]) / 2, 3)} for n, r, _ in self._spots()]

    async def observe(self, device_id: str) -> dict[str, Any] | None:
        """Known-label post data (no vision call); None when no post is on screen."""
        with self._lock:
            return feed.known_post(self._post, self._els()) if self._screen == "tt_post" else None

    async def describe(self, device_id: str) -> str:
        with self._lock:
            parts = [f"{n} at x={(r[0] + r[2]) / 2:.2f}, y={(r[1] + r[3]) / 2:.2f}" for n, r, _ in self._spots()]
            cap = f' Caption typed: "{self._caption}".' if self._screen == "caption" and self._caption else ""
            if self._screen == "tt_post":
                cap = " " + feed.post_text(self._post)
            elif self._screen in ("spotlight", "tt_search"):
                cap = f' Typed: "{self._query}".' if self._query else ""
            return f"Screen: {self._title()}.{cap} Tappable: " + "; ".join(parts) + f". Last action: {self._last}."

    async def screenshot(self, device_id: str) -> bytes:
        with self._lock:
            img = Image.new("RGB", (W, H), "#f3f4f6")
            d = ImageDraw.Draw(img)
            d.rectangle((0, 0, W, 110), fill="#111827")
            d.text((30, 55), self._title(), fill="white", font=_font(38), anchor="lm")
            d.text((W - 30, 55), time.strftime("%H:%M"), fill="#9ca3af", font=_font(30), anchor="rm")
            for name, (x0, y0, x1, y1), _ in self._spots():
                d.rectangle((x0 * W, y0 * H, x1 * W, y1 * H), outline="#2563eb", width=4, fill="#dbeafe")
                d.text(((x0 + x1) * W / 2, (y0 + y1) * H / 2), name, fill="#1e3a8a", font=_font(32), anchor="mm")
            if self._screen == "tt_post":
                feed.draw_post(d, self._post, _font)
            elif self._screen in ("spotlight", "tt_search"):
                d.text((60, 190), self._query or "(type here)", fill="#111827", font=_font(32))
            if note := SCREENS[self._screen].get("note"):
                d.text((40, 600), note, fill="#374151", font=_font(28))
            if self._screen == "caption":
                d.text((60, 300), self._caption or "(empty)", fill="#111827", font=_font(30))
            d.rectangle((0, H - 70, W, H), fill="#e5e7eb")
            d.text((20, H - 35), f"last: {self._last}"[:60], fill="#374151", font=_font(26), anchor="lm")
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=80)
            return buf.getvalue()

    async def send(self, device_id: str, action: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        with self._lock:
            if idempotency_key in self._receipts:
                return self._receipts[idempotency_key]
            rid = uuid4().hex[:12]
            err = self._apply(action)
            receipt = {"request_id": rid, "ok": err is None, "error": err, "screen": self._screen}
            self._receipts[idempotency_key] = receipt
            return receipt

    def _apply(self, a: dict[str, Any]) -> str | None:
        t = a.get("type")
        if t == "tap":
            x, y = float(a.get("x", -1)), float(a.get("y", -1))
            if not (0 <= x <= 1 and 0 <= y <= 1):
                return "invalid_coordinates"
            hit = next(((n, to) for n, (x0, y0, x1, y1), to in self._spots() if x0 <= x <= x1 and y0 <= y <= y1), None)
            self._last = f"tap {hit[0] if hit else 'nothing'} ({x:.2f},{y:.2f})"
            if hit and hit[1]:
                self._query = "" if self._screen == "spotlight" else self._query
                self._screen, _, n = hit[1].partition(":")
                self._post = int(n) if n else self._post
        elif t == "swipe":
            dy = float(a.get("from_y", 0.5)) - float(a.get("to_y", 0.5))
            if self._screen == "tt_post" and abs(dy) >= 0.3:
                self._post = min(len(feed.POSTS) - 1, max(0, self._post + (1 if dy > 0 else -1)))
                self._last = f"swipe {'up' if dy > 0 else 'down'}: post {self._post + 1}/{len(feed.POSTS)}"
            elif self._screen == "home" and dy <= -0.2:
                self._screen, self._query, self._last = "spotlight", "", "swipe down: Spotlight"
            else:
                self._last = "swipe"
        elif t == "type":
            text = str(a.get("text", ""))
            if len(text) > 512 or not set(text) <= _ASCII_OK:
                return "invalid_text"
            if self._screen == "caption":
                self._caption += text
            elif self._screen in ("spotlight", "tt_search"):
                self._query = (self._query + text)[:80]
            self._last = f"type {len(text)} chars"
        elif t == "home":
            self._screen, self._last = "home", "home"
        else:
            return "unsupported_action"
        return None

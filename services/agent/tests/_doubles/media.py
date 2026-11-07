"""Deterministic fake media provider: same catalog, timed lifecycle, SVG data-URI outputs.

queued -> in_progress after `t_progress` s -> completed after `t_done` s (default 2 s / 6 s).
Prompt markers inject faults: [fake:fail] -> failed, [fake:nsfw] -> nsfw.
"""
from __future__ import annotations

import time
from base64 import b64encode
from collections.abc import Callable
from html import escape
from typing import Any
from uuid import uuid4

from ugecy.integrations.media.catalog import catalog_models
from ugecy.interfaces import MediaJob
from ugecy.settings import Settings

_PRICE = {"image": 0.09, "video": 0.5, "audio": 0.05}


def placeholder_svg(kind: str, model: str, prompt: str) -> str:
    """9:16 SVG placeholder as a data URI (for video this is the poster frame)."""
    play = '<polygon points="215,520 215,640 315,580" fill="#fff" opacity=".9"/>' if kind == "video" else ""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="540" height="960" viewBox="0 0 540 960">'
        '<rect width="540" height="960" fill="#1f2937"/>'
        f'<text x="40" y="90" fill="#9ca3af" font-size="26" font-family="sans-serif">FAKE {kind.upper()} - {escape(model[-28:])}</text>'
        f'<text x="40" y="150" fill="#e5e7eb" font-size="24" font-family="sans-serif">{escape(prompt[:48])}</text>{play}</svg>'
    )
    return "data:image/svg+xml;base64," + b64encode(svg.encode()).decode()


class FakeMediaProvider:
    name = "fake-media"
    mode = "live"

    def __init__(self, settings: Settings | None = None, *, t_progress: float = 2.0, t_done: float = 6.0,
                 clock: Callable[[], float] = time.monotonic):
        self._t = (t_progress, t_done)
        self._clock = clock
        self._jobs: dict[str, dict[str, Any]] = {}
        self._by_key: dict[str, str] = {}

    def models(self, kind: str | None = None) -> list[dict[str, Any]]:
        return catalog_models(kind)

    async def estimate(self, model: str, args: dict[str, Any]) -> float | None:
        m = next((m for m in catalog_models() if m["endpoint_id"] == model), None)
        if not m:
            return None
        return round(_PRICE[m["kind"]] * float(args.get("batch_size") or 1) * (float(args.get("duration") or 5) / 5 if m["kind"] == "video" else 1), 3)

    async def submit(self, model: str, args: dict[str, Any], *, idempotency_key: str) -> MediaJob:
        if idempotency_key in self._by_key:  # same key -> same job, never a second "charge"
            return await self.get(self._by_key[idempotency_key])
        m = next((m for m in catalog_models() if m["endpoint_id"] == model), None)
        if not m:
            raise ValueError(f"unknown model: {model}")
        job_id = f"fake-{uuid4().hex[:12]}"
        self._jobs[job_id] = {"t0": self._clock(), "kind": m["kind"], "model": model, "prompt": str(args.get("prompt", ""))}
        self._by_key[idempotency_key] = job_id
        return MediaJob(job_id=job_id, status="queued")

    async def get(self, job_id: str) -> MediaJob:
        j = self._jobs.get(job_id)
        if not j:
            return MediaJob(job_id=job_id, status="failed", error="unknown job")
        elapsed = self._clock() - j["t0"]
        if elapsed < self._t[0]:
            return MediaJob(job_id=job_id, status="queued")
        if elapsed < self._t[1]:
            return MediaJob(job_id=job_id, status="in_progress")
        if "[fake:fail]" in j["prompt"]:
            return MediaJob(job_id=job_id, status="failed", error="fake failure injected")
        if "[fake:nsfw]" in j["prompt"]:
            return MediaJob(job_id=job_id, status="nsfw", error="fake nsfw injected")
        # shortcut: video output is the SVG poster only (no bundled mp4 without new deps); add a real clip when a player needs it
        return MediaJob(job_id=job_id, status="completed", outputs=[{"url": placeholder_svg(j["kind"], j["model"], j["prompt"]), "kind": j["kind"]}])

    async def upload(self, data: bytes, content_type: str) -> str:
        """Fake storage: echoes the bytes back as a data URI (no network)."""
        return f"data:{content_type};base64," + b64encode(data).decode()

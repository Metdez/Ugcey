"""Helpers tools use to talk to the UI stream and find their thread.

Tools call `emit("source.added", source=Source(...).model_dump())`; the stream adapter
(ugecy/stream/) turns LangGraph `custom` parts whose dict has "type" in CUSTOM_TYPES into UiEvents.
Outside a run (tests, background jobs) emit() is a no-op.
"""
from __future__ import annotations

from typing import Any

from langgraph.config import get_config, get_stream_writer

CUSTOM_TYPES = {"source.added", "asset.updated", "memory.updated", "progress"}


def emit(event_type: str, **fields: Any) -> None:
    if event_type not in CUSTOM_TYPES:
        raise ValueError(f"unknown custom event type: {event_type}")
    try:
        writer = get_stream_writer()
    except RuntimeError:  # not inside a runnable context
        return
    writer({"type": event_type, **fields})


def current_thread_id() -> str | None:
    try:
        return get_config().get("configurable", {}).get("thread_id")
    except RuntimeError:
        return None

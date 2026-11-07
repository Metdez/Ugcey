"""Shared helper: subagent prompts live in agents/prompts/<name>.md."""
from __future__ import annotations

from importlib.resources import files


def load_prompt(name: str) -> str:
    return files("ugecy.agents").joinpath("prompts", f"{name}.md").read_text(encoding="utf-8").strip()

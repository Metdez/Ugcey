"""Reads catalog.yaml (package data) once; shared by the live and off media providers."""
from __future__ import annotations

from functools import lru_cache
from importlib import resources
from typing import Any

import yaml


@lru_cache
def _load() -> tuple[dict[str, Any], ...]:
    text = resources.files(__package__).joinpath("catalog.yaml").read_text(encoding="utf-8")
    return tuple(yaml.safe_load(text)["models"])


def catalog_models(kind: str | None = None) -> list[dict[str, Any]]:
    return [dict(m) for m in _load() if kind in (None, m["kind"])]

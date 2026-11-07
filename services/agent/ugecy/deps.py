"""Process-wide dependency container. Implementations are looked up by import path so a
provider can be swapped by editing one line (or env var) without touching callers."""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

from ugecy.contracts import ProviderModes
from ugecy.interfaces import (
    AnalyticsProvider,
    AppStore,
    DeviceProvider,
    EdgeBindings,
    KVStore,
    MediaProvider,
    Publisher,
    ResearchProvider,
)
from ugecy.settings import Settings, get_settings

# kind -> mode -> "module:attr". Every class is constructed as cls(settings).
IMPLEMENTATIONS: dict[str, dict[str, str]] = {
    "kv": {"edge": "ugecy.persistence.kv:EdgeKV", "local": "ugecy.persistence.kv:SqliteKV",
           "test": "ugecy.persistence.kv:MemoryKV"},
    "app": {"edge": "ugecy.persistence.appstore:D1AppStore", "local": "ugecy.persistence.appstore:SqliteAppStore",
            "test": "ugecy.persistence.appstore:SqliteAppStore"},
    "edge": {"edge": "ugecy.persistence.edge:EdgeBindingsClient", "local": "ugecy.persistence.edge:LocalEdgeBindings",
             "test": "ugecy.persistence.edge:LocalEdgeBindings"},
    "research": {"live": "ugecy.integrations.research.web:WebResearchProvider",
                 "mock": "ugecy.integrations.research.mock:MockResearchProvider"},
    "media": {"live": "ugecy.integrations.media.higgsfield:HiggsfieldProvider",
              "mock": "ugecy.integrations.media.mock:MockMediaProvider"},
    "device": {"auto": "ugecy.integrations.device.auto:AutoDeviceProvider",
               "live": "ugecy.integrations.device.glasshand:GlasshandProvider",
               "mock": "ugecy.integrations.device.mock:MockDeviceProvider"},
    "publisher": {"mock": "ugecy.integrations.publishing.mock:MockPublisher"},
    "analytics": {"mock": "ugecy.integrations.publishing.analytics:MockAnalytics"},
}


def _load(kind: str, mode: str, settings: Settings) -> Any:
    module, attr = IMPLEMENTATIONS[kind][mode].split(":")
    return getattr(importlib.import_module(module), attr)(settings)


def resolve_modes(s: Settings) -> ProviderModes:
    local = s.internal_mode != "edge"

    def pick(choice: str, available: bool) -> str:
        return "mock" if choice == "mock" or (choice == "auto" and not available) else "live"

    media_ok = bool(s.higgsfield_key) if local else s.has_higgsfield
    device_ok = s.has_glasshand  # Glasshand needs an operator device-flow token (Settings UI), never env
    return ProviderModes(
        llm="live" if s.internal_mode != "test" else "mock",
        media=pick(s.media_provider, media_ok and s.internal_mode != "test"),  # type: ignore[arg-type]
        device=pick(s.device_provider, device_ok),  # type: ignore[arg-type]
        publishing="mock",  # official social APIs need app review; see FEATURES.md
        research=pick(s.research_provider, s.internal_mode != "test"),  # type: ignore[arg-type]
    )


@dataclass
class Deps:
    settings: Settings
    modes: ProviderModes
    kv: KVStore
    app: AppStore
    edge: EdgeBindings
    research: ResearchProvider
    media: MediaProvider
    device: DeviceProvider
    publisher: Publisher
    analytics: AnalyticsProvider
    checkpointer: Any = None  # langgraph checkpointer (set by ugecy.main at startup)
    store: Any = None  # langgraph BaseStore (set by ugecy.main at startup)


_DEPS: Deps | None = None


def build_deps(settings: Settings | None = None) -> Deps:
    s = settings or get_settings()
    m = resolve_modes(s)
    infra = s.internal_mode
    return Deps(
        settings=s, modes=m,
        kv=_load("kv", infra, s), app=_load("app", infra, s), edge=_load("edge", infra, s),
        research=_load("research", m.research, s), media=_load("media", m.media, s),
        device=_load("device", "auto" if s.device_provider == "auto" else m.device, s), publisher=_load("publisher", "mock", s),
        analytics=_load("analytics", "mock", s),
    )


def get_deps() -> Deps:
    global _DEPS
    if _DEPS is None:
        _DEPS = build_deps()
    return _DEPS


def set_deps(deps: Deps | None) -> None:
    """Tests and app startup install a prepared container."""
    global _DEPS
    _DEPS = deps

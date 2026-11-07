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
                 "off": "ugecy.integrations.research.web:WebResearchProvider"},  # fetch_page still works; search is off
    "media": {"live": "ugecy.integrations.media.higgsfield:HiggsfieldProvider",
              "off": "ugecy.integrations.unavailable:OffMediaProvider"},
    "device": {"auto": "ugecy.integrations.device.auto:AutoDeviceProvider",
               "live": "ugecy.integrations.device.glasshand:GlasshandProvider",
               "off": "ugecy.integrations.unavailable:OffDeviceProvider"},
    "publisher": {"off": "ugecy.integrations.unavailable:OffPublisher"},
    "analytics": {"off": "ugecy.integrations.unavailable:OffAnalytics"},
}

# Test doubles live under tests/ and are loadable only when internal_mode == "test".
_TEST_DOUBLES: dict[str, str] = {
    "research": "tests._doubles.research:MockResearchProvider",
    "media": "tests._doubles.media:MockMediaProvider",
    "device": "tests._doubles.device:MockDeviceProvider",
    "publisher": "tests._doubles.publisher:MockPublisher",
    "analytics": "tests._doubles.analytics:MockAnalytics",
}


def _load(kind: str, mode: str, settings: Settings) -> Any:
    if mode == "mock":
        if settings.internal_mode != "test":
            raise RuntimeError("mock providers are only available when UGECY_INTERNAL_MODE=test")
        path = _TEST_DOUBLES[kind]
    else:
        path = IMPLEMENTATIONS[kind][mode]
    module, attr = path.split(":")
    return getattr(importlib.import_module(module), attr)(settings)


def resolve_modes(s: Settings) -> ProviderModes:
    """live when configured, otherwise off. "mock" is returned only in test mode, and only when asked for."""
    local = s.internal_mode != "edge"

    def pick(choice: str, configured: bool) -> str:
        if choice == "mock" and s.internal_mode == "test":
            return "mock"
        return "live" if configured and choice != "off" and s.internal_mode != "test" else "off"  # tests never reach live

    media_ok = bool(s.higgsfield_key) if local else s.has_higgsfield
    search_ok = bool(s.firecrawl_api_key) if local else s.has_firecrawl
    return ProviderModes(
        llm="live" if s.internal_mode != "test" else "mock",
        media=pick(s.media_provider, media_ok),  # type: ignore[arg-type]
        device=pick(s.device_provider, bool(s.glasshand_token) if local else s.has_glasshand),  # type: ignore[arg-type]
        publishing="mock" if s.publishing_provider == "mock" and s.internal_mode == "test" else "off",  # no live API publisher yet
        research=pick(s.research_provider, search_ok),  # type: ignore[arg-type]
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
        device=_load("device", "auto" if s.device_provider == "auto" else m.device, s),
        publisher=_load("publisher", "mock" if m.publishing == "mock" else "off", s),
        analytics=_load("analytics", "mock" if m.publishing == "mock" else "off", s),
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

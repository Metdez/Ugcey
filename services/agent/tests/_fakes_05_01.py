"""Fakes for phone-research tests (plan 05-01): deps with a recording app store."""
from __future__ import annotations

from tests._doubles.device import FakeDeviceProvider
from ugecy.contracts import ProviderModes
from ugecy.deps import Deps, set_deps
from ugecy.settings import Settings
from ugecy.tools import device


class MemApp:
    def __init__(self):
        self.audit, self.sources = [], []

    async def add_audit(self, e): self.audit.append(e)
    async def add_source(self, tid, s): self.sources.append((tid, s))


def install(monkeypatch, provider=None) -> tuple[Deps, list[float], list[dict]]:
    """Returns (deps, an empty legacy delay list, emitted source events); resets device state."""
    d = Deps(settings=Settings(internal_mode="test"), modes=ProviderModes(media="live", device="live", publishing="live", research="live"), kv=None, app=MemApp(), edge=None,  # type: ignore[arg-type]
             research=None, media=None, device=provider or FakeDeviceProvider(), publisher=None, analytics=None)  # type: ignore[arg-type]
    set_deps(d)
    device.reset_state()
    slept: list[float] = []
    events: list[dict] = []

    monkeypatch.setattr(device, "current_thread_id", lambda: "t1")
    monkeypatch.setattr(device, "emit", lambda t, **f: events.append({"type": t, **f}))
    return d, slept, events

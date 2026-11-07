"""Fakes for phone-research tests (plan 05-01): deps with a recording app store and a sleep recorder."""
from __future__ import annotations

from tests._doubles.device import MockDeviceProvider
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
    """Returns (deps, recorded sleep seconds, emitted source events); resets device state."""
    d = Deps(settings=Settings(internal_mode="test"), modes=ProviderModes(media="mock", device="mock", publishing="mock", research="mock"), kv=None, app=MemApp(), edge=None,  # type: ignore[arg-type]
             research=None, media=None, device=provider or MockDeviceProvider(), publisher=None, analytics=None)  # type: ignore[arg-type]
    set_deps(d)
    device.reset_state()
    slept: list[float] = []
    events: list[dict] = []

    async def fake_sleep(s: float) -> None:
        slept.append(s)

    device.set_sleep(fake_sleep)
    monkeypatch.setattr(device, "current_thread_id", lambda: "t1")
    monkeypatch.setattr(device, "emit", lambda t, **f: events.append({"type": t, **f}))
    return d, slept, events

"""In-memory app store / edge and a Deps builder for the production-tools tests (plan 02-08)."""
from __future__ import annotations

from tests._doubles.device import FakeDeviceProvider
from tests._doubles.media import FakeMediaProvider
from tests._doubles.publisher import FakePublisher
from ugecy.contracts import ProviderModes
from ugecy.deps import Deps, set_deps
from ugecy.settings import Settings


class MemApp:
    def __init__(self):
        self.audit, self.assets, self.posts, self.accounts = [], {}, {}, {}

    async def add_audit(self, e): self.audit.append(e)
    async def upsert_asset(self, a): self.assets[a.id] = a
    async def get_asset(self, i): return self.assets.get(i)
    async def upsert_post(self, p): self.posts[p.id] = p
    async def get_post(self, i): return self.posts.get(i)
    async def upsert_account(self, a): self.accounts[a.id] = a
    async def list_accounts(self): return list(self.accounts.values())


class FakeEdge:
    def __init__(self):
        self.ingested, self.scheduled = [], []

    async def media_ingest(self, asset_id, url, kind):
        self.ingested.append((asset_id, url, kind))
        return {"asset_id": asset_id}

    async def schedule_publish(self, post_id, publish_at):
        self.scheduled.append((post_id, publish_at))
        return "wf-1"


def install(media=None, internal_mode="test") -> Deps:
    s = Settings(internal_mode=internal_mode)
    d = Deps(settings=s, modes=ProviderModes(media="live", device="live", publishing="live", research="live"), kv=None, app=MemApp(), edge=FakeEdge(), research=None,  # type: ignore[arg-type]
             media=media or FakeMediaProvider(t_progress=0.0, t_done=0.0), device=FakeDeviceProvider(), publisher=FakePublisher(),
             analytics=None)  # type: ignore[arg-type]
    set_deps(d)
    return d

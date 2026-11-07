"""Seams between modules. Each Protocol has a live implementation and an Off one (ugecy.integrations.unavailable).

Owners (see .planning/phases/02-build/): persistence/* implements KVStore, AppStore, EdgeBindings;
integrations/* implements the providers. Tools call providers only through ugecy.deps.get_deps().
"""
from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from ugecy.contracts import (
    ApprovalRecord,
    Asset,
    AuditEntry,
    ConnectedAccount,
    DeviceInfo,
    Mode,
    Post,
    Source,
    ThreadSummary,
)

# LangGraph Store namespaces (values are deepagents FileData dicts:
# {"content": str, "encoding": "utf-8", "created_at": iso, "modified_at": iso}; key = path after the route,
# e.g. "/memories/AGENTS.md" is stored under MEMORIES_NS(ws) with key "/AGENTS.md").
SKILLS_NS: tuple[str, ...] = ("global", "skills")


def memories_ns(workspace_id: str) -> tuple[str, ...]:
    return (workspace_id, "memories")


# ---- persistence -------------------------------------------------------------------------

class KVStore(Protocol):
    """Namespaced byte KV (state.internal / sqlite / memory). Backs checkpointer + store mirrors."""

    async def get(self, ns: str, prefix: str = "") -> dict[str, bytes]: ...
    async def put(self, ns: str, items: dict[str, bytes]) -> None: ...
    async def delete(self, ns: str, prefix: str = "") -> int: ...


class AppStore(Protocol):
    """System of record (D1 at the edge, sqlite locally). Schema: migrations/0001_init.sql."""

    async def init(self) -> None: ...
    async def upsert_thread(self, thread: ThreadSummary) -> None: ...
    async def get_thread(self, thread_id: str) -> ThreadSummary | None: ...
    async def list_threads(self) -> list[ThreadSummary]: ...
    async def delete_thread(self, thread_id: str) -> None: ...
    async def add_audit(self, entry: AuditEntry) -> None: ...
    async def list_audit(self, thread_id: str | None = None, limit: int = 100) -> list[AuditEntry]: ...
    async def upsert_asset(self, asset: Asset) -> None: ...
    async def get_asset(self, asset_id: str) -> Asset | None: ...
    async def list_assets(self, thread_id: str | None = None) -> list[Asset]: ...
    async def upsert_post(self, post: Post) -> None: ...
    async def get_post(self, post_id: str) -> Post | None: ...
    async def list_posts(self, thread_id: str | None = None) -> list[Post]: ...
    async def upsert_account(self, account: ConnectedAccount) -> None: ...
    async def list_accounts(self) -> list[ConnectedAccount]: ...
    async def upsert_approval(self, record: ApprovalRecord) -> None: ...
    async def get_approval(self, interrupt_id: str) -> ApprovalRecord | None: ...
    async def list_approvals(self, status: str | None = None) -> list[ApprovalRecord]: ...
    async def add_source(self, thread_id: str, source: Source) -> None: ...  # idempotent per (thread, url)
    async def list_sources(self, thread_id: str) -> list[Source]: ...


class EdgeBindings(Protocol):
    """bindings.internal (non-D1 parts). Local impl uses httpx / memory / no-ops."""

    async def browser_markdown(self, url: str) -> dict[str, str]: ...  # {url, title, markdown}
    async def vectors_upsert(self, namespace: str, items: list[dict[str, Any]]) -> int: ...  # {id,text,metadata}
    async def vectors_query(self, namespace: str, text: str, top_k: int = 5) -> list[dict[str, Any]]: ...
    async def media_ingest(self, asset_id: str, url: str, kind: str) -> dict[str, Any]: ...
    async def schedule_publish(self, post_id: str, publish_at: str | None) -> str: ...  # workflow id
    async def metric(self, event: str, blobs: list[str], doubles: list[float]) -> None: ...


# ---- providers ---------------------------------------------------------------------------

class ResearchProvider(Protocol):
    name: str
    mode: Mode

    async def search(self, query: str, platform: str | None = None, limit: int = 8) -> list[Source]: ...
    async def fetch(self, url: str) -> dict[str, Any]: ...  # {url, title, platform, markdown, metrics?}


class MediaJob(BaseModel):
    job_id: str
    status: Literal["queued", "in_progress", "completed", "failed", "nsfw", "canceled"]
    outputs: list[dict[str, str]] = Field(default_factory=list)  # [{url, kind}]
    error: str | None = None


class MediaProvider(Protocol):
    name: str
    mode: Mode

    def models(self, kind: str | None = None) -> list[dict[str, Any]]: ...  # [{endpoint_id, kind, label, defaults}]
    async def estimate(self, model: str, args: dict[str, Any]) -> float | None: ...
    async def submit(self, model: str, args: dict[str, Any], *, idempotency_key: str) -> MediaJob: ...
    async def get(self, job_id: str) -> MediaJob: ...


class DeviceProvider(Protocol):
    name: str
    mode: Mode

    async def list_devices(self) -> list[DeviceInfo]: ...
    async def screenshot(self, device_id: str) -> bytes: ...  # JPEG
    async def describe(self, device_id: str) -> str: ...  # short text of what is on screen
    async def send(self, device_id: str, action: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]: ...


class Publisher(Protocol):
    name: str
    mode: Mode

    async def publish(self, post: Post, asset: Asset | None) -> dict[str, Any]: ...  # {status, external_url}


class AnalyticsProvider(Protocol):
    name: str
    mode: Mode

    async def post_metrics(self, posts: list[Post]) -> list[dict[str, Any]]: ...

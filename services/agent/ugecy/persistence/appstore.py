"""AppStore (system of record) over a SqlExecutor: D1 at the edge, sqlite locally. One schema file."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

import httpx
from pydantic import BaseModel

from ugecy.contracts import (
    ApprovalRecord,
    Asset,
    AuditEntry,
    ConnectedAccount,
    Post,
    Source,
    ThreadSummary,
    now_iso,
)
from ugecy.internal import post_json
from ugecy.persistence._sqlite import SqliteDB, db_path
from ugecy.settings import Settings

SCHEMA = Path(__file__).with_name("schema.sql")
_UP = Path(__file__).resolve().parents
REPO_MIGRATION = (_UP[4] / "migrations" / "0001_init.sql") if len(_UP) > 4 else Path("/nonexistent")  # absent in the container


class SqlExecutor(Protocol):
    async def query(self, sql: str, params: list[Any] | tuple = ()) -> list[dict[str, Any]]: ...
    async def execute(self, sql: str, params: list[Any] | tuple = ()) -> None: ...


class _D1Executor:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None):
        self._s, self._http = settings, http

    async def query(self, sql: str, params: list[Any] | tuple = ()) -> list[dict[str, Any]]:
        r = await post_json("bindings.internal", "/d1/query", {"sql": sql, "params": list(params)},
                            http=self._http, settings=self._s)
        return r["results"]

    async def execute(self, sql: str, params: list[Any] | tuple = ()) -> None:
        await self.query(sql, params)


def _upsert(table: str, cols: list[str], pk: list[str]) -> str:
    sets = ", ".join(f"{c}=excluded.{c}" for c in cols if c not in pk)
    return (f"INSERT INTO {table}({', '.join(cols)}) VALUES({', '.join('?' * len(cols))}) "
            f"ON CONFLICT({', '.join(pk)}) DO UPDATE SET {sets}")


def _cols(model: type[BaseModel]) -> list[str]:
    return list(model.model_fields)


def _dump(m: BaseModel) -> list[Any]:
    out = []
    for name in type(m).model_fields:
        v = getattr(m, name)
        if isinstance(v, bool):
            v = int(v)
        elif name == "requests":
            v = json.dumps([r.model_dump(mode="json") for r in v])
        out.append(v)
    return out


def _load[M: BaseModel](model: type[M], row: dict[str, Any]) -> M:
    row = dict(row)
    if "requests" in row:
        row["requests"] = json.loads(row["requests"])
    if "ai_disclosure" in row:
        row["ai_disclosure"] = bool(row["ai_disclosure"])
    return model.model_validate({k: v for k, v in row.items() if k in model.model_fields})


class SqlAppStore:
    def __init__(self, db: SqlExecutor):
        self.db = db

    async def init(self) -> None: ...

    async def _get[M: BaseModel](self, model: type[M], table: str, pk: str, value: str) -> M | None:
        rows = await self.db.query(f"SELECT * FROM {table} WHERE {pk}=?", [value])
        return _load(model, rows[0]) if rows else None

    async def _list[M: BaseModel](self, model: type[M], table: str, order: str, where: str = "", params: list[Any] | None = None,
                    limit: int | None = None) -> list[M]:
        sql = f"SELECT * FROM {table} {where} ORDER BY {order}" + (f" LIMIT {int(limit)}" if limit else "")
        return [_load(model, r) for r in await self.db.query(sql, params or [])]

    async def _put(self, table: str, m: BaseModel, pk: str) -> None:
        await self.db.execute(_upsert(table, _cols(type(m)), [pk]), _dump(m))

    # threads
    async def upsert_thread(self, thread: ThreadSummary) -> None:
        await self._put("threads", thread, "id")

    async def get_thread(self, thread_id: str) -> ThreadSummary | None:
        return await self._get(ThreadSummary, "threads", "id", thread_id)

    async def list_threads(self) -> list[ThreadSummary]:
        return await self._list(ThreadSummary, "threads", "updated_at DESC")

    async def delete_thread(self, thread_id: str) -> None:
        for table, col in (("sources", "thread_id"), ("approvals", "thread_id"), ("threads", "id")):
            await self.db.execute(f"DELETE FROM {table} WHERE {col}=?", [thread_id])
        # audit/assets/posts are records of what happened: they outlive the thread.

    # audit
    async def add_audit(self, entry: AuditEntry) -> None:
        await self._put("audit", entry, "id")

    async def list_audit(self, thread_id: str | None = None, limit: int = 100) -> list[AuditEntry]:
        where, params = ("WHERE thread_id=?", [thread_id]) if thread_id else ("", [])
        return await self._list(AuditEntry, "audit", "ts DESC", where, params, limit)

    # assets
    async def upsert_asset(self, asset: Asset) -> None:
        await self._put("assets", asset, "id")

    async def get_asset(self, asset_id: str) -> Asset | None:
        return await self._get(Asset, "assets", "id", asset_id)

    async def list_assets(self, thread_id: str | None = None) -> list[Asset]:
        where, params = ("WHERE thread_id=?", [thread_id]) if thread_id else ("", [])
        return await self._list(Asset, "assets", "created_at DESC", where, params)

    # posts
    async def upsert_post(self, post: Post) -> None:
        await self._put("posts", post, "id")

    async def get_post(self, post_id: str) -> Post | None:
        return await self._get(Post, "posts", "id", post_id)

    async def list_posts(self, thread_id: str | None = None) -> list[Post]:
        where, params = ("WHERE thread_id=?", [thread_id]) if thread_id else ("", [])
        return await self._list(Post, "posts", "created_at DESC", where, params)

    # accounts
    async def upsert_account(self, account: ConnectedAccount) -> None:
        await self._put("accounts", account, "id")

    async def list_accounts(self) -> list[ConnectedAccount]:
        return await self._list(ConnectedAccount, "accounts", "id")

    # approvals
    async def upsert_approval(self, record: ApprovalRecord) -> None:
        await self._put("approvals", record, "interrupt_id")

    async def get_approval(self, interrupt_id: str) -> ApprovalRecord | None:
        return await self._get(ApprovalRecord, "approvals", "interrupt_id", interrupt_id)

    async def list_approvals(self, status: str | None = None) -> list[ApprovalRecord]:
        where, params = ("WHERE status=?", [status]) if status else ("", [])
        return await self._list(ApprovalRecord, "approvals", "created_at DESC", where, params)

    # sources
    async def add_source(self, thread_id: str, source: Source) -> None:
        await self.db.execute(
            "INSERT INTO sources(thread_id,url,title,platform,snippet,created_at) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(thread_id,url) DO NOTHING",
            [thread_id, source.url, source.title, source.platform, source.snippet, now_iso()])

    async def list_sources(self, thread_id: str) -> list[Source]:
        return await self._list(Source, "sources", "created_at, rowid", "WHERE thread_id=?", [thread_id])


class SqliteAppStore(SqlAppStore):
    def __init__(self, settings: Settings):
        self._sqlite = SqliteDB(db_path(settings, "app.db"))
        super().__init__(self._sqlite)

    async def init(self) -> None:
        path = REPO_MIGRATION if REPO_MIGRATION.exists() else SCHEMA
        await self._sqlite.script(path.read_text())


class D1AppStore(SqlAppStore):
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None):
        super().__init__(_D1Executor(settings, http))
        # init() stays a no-op: the Worker applies migrations to D1.

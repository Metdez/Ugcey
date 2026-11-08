"""KVStore implementations: EdgeKV (state.internal), SqliteKV (.ugecy/state.db), MemoryKV (tests)."""
from __future__ import annotations

import base64

import httpx

from ugecy.internal import post_json
from ugecy.persistence._sqlite import SqliteDB, db_path
from ugecy.settings import Settings

MAX_ITEMS = 200
MAX_BYTES = 4 * 1024 * 1024


class MemoryKV:
    def __init__(self, settings: Settings | None = None):
        self._d: dict[str, dict[str, bytes]] = {}

    async def get(self, ns: str, prefix: str = "") -> dict[str, bytes]:
        d = self._d.get(ns, {})
        return {k: d[k] for k in sorted(d) if k.startswith(prefix)}

    async def put(self, ns: str, items: dict[str, bytes]) -> None:
        self._d.setdefault(ns, {}).update(items)

    async def delete(self, ns: str, prefix: str = "") -> int:
        d = self._d.get(ns, {})
        gone = [k for k in d if k.startswith(prefix)]
        for k in gone:
            del d[k]
        return len(gone)


class SqliteKV:
    def __init__(self, settings: Settings):
        self._db = SqliteDB(db_path(settings, "state.db"))
        self._ready = False

    async def _init(self) -> None:
        if not self._ready:
            await self._db.script("CREATE TABLE IF NOT EXISTS kv(ns TEXT NOT NULL, key TEXT NOT NULL, "
                                  "value BLOB NOT NULL, updated_at INTEGER, PRIMARY KEY(ns, key))")
            self._ready = True

    async def get(self, ns: str, prefix: str = "") -> dict[str, bytes]:
        await self._init()
        rows = await self._db.query("SELECT key, value FROM kv WHERE ns=? AND substr(key,1,length(?))=? ORDER BY key",
                                    (ns, prefix, prefix))
        return {r["key"]: bytes(r["value"]) for r in rows}

    async def put(self, ns: str, items: dict[str, bytes]) -> None:
        await self._init()
        for k, v in items.items():
            await self._db.execute(
                "INSERT INTO kv(ns,key,value,updated_at) VALUES(?,?,?,strftime('%s','now')) "
                "ON CONFLICT(ns,key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (ns, k, v))

    async def delete(self, ns: str, prefix: str = "") -> int:
        await self._init()
        n = len(await self.get(ns, prefix))
        await self._db.execute("DELETE FROM kv WHERE ns=? AND substr(key,1,length(?))=?", (ns, prefix, prefix))
        return n


def _chunks(items: dict[str, bytes]):
    """Yield wire items in groups of <= MAX_ITEMS entries and <= MAX_BYTES of base64 payload."""
    chunk: list[dict[str, str]] = []
    size = 0
    for k, v in items.items():
        b64 = base64.b64encode(v).decode()
        if chunk and (len(chunk) >= MAX_ITEMS or size + len(b64) > MAX_BYTES):
            yield chunk
            chunk, size = [], 0
        chunk.append({"key": k, "value_b64": b64})
        size += len(b64)
    if chunk:
        yield chunk


class EdgeKV:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None):
        self._s, self._http = settings, http

    async def _post(self, path: str, body: dict) -> dict:
        return await post_json("state.internal", path, body, http=self._http, settings=self._s)

    async def get(self, ns: str, prefix: str = "") -> dict[str, bytes]:
        out: dict[str, bytes] = {}
        after = ""
        while True:  # paged: the DO returns <= ~2 MB per call so large threads never exhaust its memory
            r = await self._post("/kv/get", {"ns": ns, "prefix": prefix, "after": after})
            out.update({i["key"]: base64.b64decode(i["value_b64"]) for i in r["items"]})
            if not r.get("next"):
                return out
            after = r["next"]

    async def put(self, ns: str, items: dict[str, bytes]) -> None:
        for chunk in _chunks(items):  # shortcut: chunks are atomic individually, not across the whole call
            await self._post("/kv/put", {"ns": ns, "items": chunk})

    async def delete(self, ns: str, prefix: str = "") -> int:
        return (await self._post("/kv/delete", {"ns": ns, "prefix": prefix}))["deleted"]

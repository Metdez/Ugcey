"""InMemoryStore mirrored write-through into KV ns `store` (memories + skills; small, hydrated at startup)."""
from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime

from langgraph.store.base import Op, PutOp, Result
from langgraph.store.memory import InMemoryStore

from ugecy.interfaces import KVStore

NS = "store"


def _key(namespace: tuple[str, ...], key: str) -> str:
    return json.dumps([*namespace, key])


class MirroredStore(InMemoryStore):
    def __init__(self, kv: KVStore, **kw):
        super().__init__(**kw)
        self.kv = kv

    async def hydrate(self) -> None:
        from langgraph.store.base import Item

        for k, raw in (await self.kv.get(NS)).items():
            *namespace, key = json.loads(k)
            d = json.loads(raw)
            self._data[tuple(namespace)][key] = Item(
                value=d["value"], key=key, namespace=tuple(namespace),
                created_at=datetime.fromisoformat(d["created_at"]), updated_at=datetime.fromisoformat(d["updated_at"]))

    async def abatch(self, ops: Iterable[Op]) -> list[Result]:
        ops = list(ops)
        results = await super().abatch(ops)
        puts = {(o.namespace, o.key): o for o in ops if isinstance(o, PutOp)}  # last write wins, like the base
        upserts: dict[str, bytes] = {}
        for (namespace, key), op in puts.items():
            if op.value is None:
                await self.kv.delete(NS, _key(namespace, key))
            else:
                item = self._data[namespace][key]
                upserts[_key(namespace, key)] = json.dumps(
                    {"value": item.value, "created_at": item.created_at.isoformat(),
                     "updated_at": item.updated_at.isoformat()}).encode()
        if upserts:
            await self.kv.put(NS, upserts)
        return results

    def batch(self, ops: Iterable[Op]) -> list[Result]:
        # shortcut: the sync path is not mirrored (deepagents + the async graph only use abatch).
        # Upgrade if a sync caller ever writes memories.
        return super().batch(ops)


async def build_store(kv: KVStore) -> MirroredStore:
    store = MirroredStore(kv)
    await store.hydrate()
    return store

"""InMemorySaver whose state is mirrored write-through into a KVStore (ns `ckpt:<thread_id>`).

Reads hit memory; a thread's latest state is hydrated from KV the first time it is touched, so a
restarted container resumes any thread. Everything stored is serde output ((type, bytes) pairs), encoded as
JSON+base64, so no arbitrary pickling is introduced."""
from __future__ import annotations

import asyncio
import base64
import json
from collections import defaultdict
from collections.abc import AsyncIterator, Sequence
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from ugecy.interfaces import KVStore


def _enc(*parts: Any) -> bytes:
    return json.dumps(parts, default=lambda b: {"b64": base64.b64encode(b).decode()}).encode()


def _typed(t: Any) -> tuple[str, bytes]:
    return t[0], base64.b64decode(t[1]["b64"])


def _ns(thread_id: str) -> str:
    return f"ckpt:{thread_id}"


class MirroredSaver(InMemorySaver):
    def __init__(self, kv: KVStore, **kw: Any):
        super().__init__(**kw)
        self.kv = kv
        self._loaded: set[str] = set()
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def _hydrate(self, thread_id: str) -> None:
        """Load each namespace's latest checkpoint with its channel blobs and pending writes.

        Older checkpoints stay in KV but are not loaded: every step stores a full copy of each changed
        channel, so a long thread's history runs to hundreds of MB. state.internal pages reads (~2 MB) so
        the Durable Object survives them, but that would still be dozens of round trips and the whole
        history held in memory. Nothing here reads them (no time travel); `aget_state_history` after a
        restart starts at the latest checkpoint."""
        if thread_id in self._loaded:
            return
        async with self._locks[thread_id]:
            if thread_id in self._loaded:
                return
            latest: dict[str, tuple[str, bytes]] = {}
            for key, raw in (await self.kv.get(_ns(thread_id), "c|")).items():
                ns, cid = json.loads(key[2:])
                if cid > latest.get(ns, ("",))[0]:  # ids sort by time, as InMemorySaver's max() relies on
                    latest[ns] = (cid, raw)
            prefixes = []
            for ns, (cid, raw) in latest.items():
                ckpt, meta, parent = json.loads(raw)
                self.storage[thread_id][ns][cid] = (_typed(ckpt), _typed(meta), parent)
                versions = self.serde.loads_typed(_typed(ckpt))["channel_versions"]
                prefixes += [f"b|{json.dumps([ns, ch, ver])}" for ch, ver in versions.items()]
                prefixes.append(f"w|{json.dumps([ns, cid])[:-1]},")  # every write key of this checkpoint
            sem = asyncio.Semaphore(16)

            async def fetch(prefix: str) -> dict[str, bytes]:
                async with sem:
                    return await self.kv.get(_ns(thread_id), prefix)

            for found in await asyncio.gather(*map(fetch, prefixes)):
                for key, raw in found.items():
                    body = json.loads(raw)
                    if key[0] == "w":
                        ns, cid, task, idx = json.loads(key[2:])
                        t, ch, val, path = body
                        self.writes[(thread_id, ns, cid)][(task, idx)] = (t, ch, _typed(val), path)
                    else:
                        ns, ch, ver = json.loads(key[2:])
                        self.blobs[(thread_id, ns, ch, ver)] = _typed(body[0])
            self._loaded.add(thread_id)

    async def aget_tuple(self, config):
        await self._hydrate(config["configurable"]["thread_id"])
        return await super().aget_tuple(config)

    async def alist(self, config, **kw) -> AsyncIterator:
        # shortcut: config=None lists only already-hydrated threads; the app always passes a thread_id.
        if config:
            await self._hydrate(config["configurable"]["thread_id"])
        async for item in super().alist(config, **kw):
            yield item

    async def aget_delta_channel_history(self, *, config, channels: Sequence[str]):
        await self._hydrate(config["configurable"]["thread_id"])
        return await super().aget_delta_channel_history(config=config, channels=channels)

    async def aput(self, config, checkpoint, metadata, new_versions):
        tid, ns = config["configurable"]["thread_id"], config["configurable"]["checkpoint_ns"]
        await self._hydrate(tid)
        async with self._locks[tid]:
            out = await super().aput(config, checkpoint, metadata, new_versions)
            ckpt, meta, parent = self.storage[tid][ns][checkpoint["id"]]
            items = {f"c|{json.dumps([ns, checkpoint['id']])}": _enc(ckpt, meta, parent)}
            for ch, ver in new_versions.items():
                items[f"b|{json.dumps([ns, ch, ver])}"] = _enc(self.blobs[(tid, ns, ch, ver)])
            await self.kv.put(_ns(tid), items)
        return out

    async def aput_writes(self, config, writes, task_id: str, task_path: str = "") -> None:
        tid = config["configurable"]["thread_id"]
        ns, cid = config["configurable"].get("checkpoint_ns", ""), config["configurable"]["checkpoint_id"]
        await self._hydrate(tid)
        async with self._locks[tid]:
            before = dict(self.writes.get((tid, ns, cid), {}))
            await super().aput_writes(config, writes, task_id, task_path)
            now = self.writes[(tid, ns, cid)]
            items = {f"w|{json.dumps([ns, cid, k[0], k[1]])}": _enc(*v[:2], v[2], v[3])
                     for k, v in now.items() if before.get(k) != v}
            if items:
                await self.kv.put(_ns(tid), items)

    async def adelete_thread(self, thread_id: str) -> None:
        await self._hydrate(thread_id)
        async with self._locks[thread_id]:
            await super().adelete_thread(thread_id)
            await self.kv.delete(_ns(thread_id))


def build_checkpointer(kv: KVStore) -> MirroredSaver:
    return MirroredSaver(kv)

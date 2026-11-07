# 02-06 Summary: persistence

## Files created
- `services/agent/ugecy/internal.py`: `client(host, settings=None)` (edge-only, one shared client per host, raises otherwise), `post_json(host, path, body, *, http=None, settings=None)`, `InternalError(code, message, status)`.
- `ugecy/persistence/_sqlite.py`: `SqliteDB` (sqlite3 under `to_thread`, lock), `db_path()` (`:memory:` in test mode).
- `ugecy/persistence/kv.py`: `MemoryKV`, `SqliteKV` (`{data_dir}/state.db`), `EdgeKV(settings, http=None)` (chunks <=200 items / <=4 MB base64).
- `ugecy/persistence/checkpointer.py`: `MirroredSaver(InMemorySaver)`, `build_checkpointer(kv)`.
- `ugecy/persistence/store.py`: `MirroredStore(InMemoryStore)`, `async build_store(kv)`.
- `ugecy/persistence/appstore.py`: `SqlAppStore`, `SqliteAppStore(settings)`, `D1AppStore(settings, http=None)`.
- `ugecy/persistence/edge.py`: `EdgeBindingsClient`, `LocalEdgeBindings`, `html_to_text`.
- `ugecy/persistence/schema.sql` (copy), `migrations/0001_init.sql`, `persistence/__init__.py` (exports factories).
- Tests: `tests/test_persistence_checkpointer.py`, `tests/test_persistence_stores.py`.

## Design notes
- Checkpointer KV keys (ns `ckpt:<thread_id>`): `c|[ns,ckpt_id]`, `w|[ns,ckpt_id,task,idx]`, `b|[ns,channel,version]`. JSON arrays in keys (checkpoint_ns can contain `|`). Values are JSON+base64 of serde `(type, bytes)`; no pickle.
- Overrides: `aget_tuple`, `alist`, `aget_delta_channel_history` (hydrate), `aput`, `aput_writes` (diff, write-through), `adelete_thread`. Per-thread asyncio.Lock.
- Store KV key = `json([*namespace, key])`; value = `{value, created_at, updated_at}`.
- `SqliteAppStore.init()` runs repo `migrations/0001_init.sql` if present, else bundled `schema.sql` (test asserts equal).
- `delete_thread` removes thread, approvals, sources; audit/assets/posts are kept as records.

## Tests
`uv run pytest -q tests/test_persistence_*.py`: 15 passed. `ruff check` clean on my files. Largest file 183 lines.
Covers restart survival (history, continue, interrupt then resume after restart, delete), store put/delete/restart/search, AppStore CRUD, EdgeKV (MockTransport, chunking by count and bytes), D1AppStore, LocalEdgeBindings.

## Deviations / shortcuts
- `alist(config=None)` lists only hydrated threads. Sync `get_tuple/put` and `MirroredStore.batch` are not mirrored (async graph only).
- EdgeKV chunks are atomic individually, not across a whole `put`.
- `sources` has an extra `created_at` column (ordering).
- No new packages.

## Change requests
- None required. `ugecy.main` must call `await store.hydrate()` via `build_store` and `await app.init()` at startup.
- Worker (`/d1/query`): must return `results` as a list of row objects for SELECT, and `[]` for writes.

## Risks
- `deps.build_deps` constructs `SqliteKV`/`SqliteAppStore` eagerly; files open lazily at first use (data_dir created at construction).
- Large threads re-hydrate fully on first touch; fine at current sizes.

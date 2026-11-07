"""Tiny async wrapper over one stdlib sqlite3 connection (run in a thread, serialized by a lock)."""
from __future__ import annotations

import asyncio
import sqlite3
import threading
from pathlib import Path
from typing import Any

from ugecy.settings import Settings


def db_path(settings: Settings, name: str) -> str:
    if settings.internal_mode == "test":
        return ":memory:"
    d = Path(settings.data_dir)
    d.mkdir(parents=True, exist_ok=True)
    return str(d / name)


class SqliteDB:
    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()

    def _run(self, sql: str, params: list[Any] | tuple, script: bool) -> list[dict[str, Any]]:
        with self._lock:
            if script:
                self._conn.executescript(sql)
                return []
            cur = self._conn.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
            self._conn.commit()
            return rows

    async def query(self, sql: str, params: list[Any] | tuple = ()) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._run, sql, params, False)

    async def execute(self, sql: str, params: list[Any] | tuple = ()) -> None:
        await asyncio.to_thread(self._run, sql, params, False)

    async def script(self, sql: str) -> None:
        await asyncio.to_thread(self._run, sql, (), True)

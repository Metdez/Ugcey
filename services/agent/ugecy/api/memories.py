"""Long-term memory and skills (the LangGraph Store). Skills are read-only."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ugecy.api.common import deps_of
from ugecy.api.errors import ApiError
from ugecy.contracts import MemoryFile, PutMemoryRequest, now_iso
from ugecy.interfaces import SKILLS_NS, memories_ns
from ugecy.stream.adapter import file_text

router = APIRouter(prefix="/api/memories")
_LIMIT = 1000


def _memory_file(prefix: str, scope: str, key: str, value: dict[str, Any], updated: Any) -> MemoryFile:
    return MemoryFile(path=prefix + key, scope=scope, content=file_text(value), editable=scope == "memories",  # type: ignore[arg-type]
                      updated_at=value.get("modified_at") or (updated.isoformat() if updated else None))


@router.get("")
async def list_memories(request: Request) -> list[MemoryFile]:
    deps = deps_of(request)
    out: list[MemoryFile] = []
    for ns, prefix, scope in ((memories_ns(deps.settings.workspace_id), "/memories", "memories"),
                              (SKILLS_NS, "/skills", "skills")):
        items = await deps.store.asearch(ns, limit=_LIMIT)
        out += [_memory_file(prefix, scope, i.key, i.value, i.updated_at) for i in sorted(items, key=lambda i: i.key)]
    return out


@router.put("")
async def put_memory(request: Request, body: PutMemoryRequest) -> MemoryFile:
    deps = deps_of(request)
    if not body.path.startswith("/memories/") or ".." in body.path.split("/") or body.path.endswith("/"):
        raise ApiError(422, "invalid_path", "path must be a file under /memories/")
    ns, key, now = memories_ns(deps.settings.workspace_id), body.path.removeprefix("/memories"), now_iso()
    existing = await deps.store.aget(ns, key)
    value = {"content": body.content, "encoding": "utf-8",
             "created_at": (existing.value.get("created_at") if existing else None) or now, "modified_at": now}
    await deps.store.aput(ns, key, value)
    return _memory_file("/memories", "memories", key, value, None)

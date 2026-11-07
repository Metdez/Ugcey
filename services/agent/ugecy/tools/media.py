"""Domain media tools. generate_media is the only side effect (it spends money): approval-gated."""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ugecy.contracts import Asset, AuditEntry
from ugecy.deps import get_deps
from ugecy.events import current_thread_id, emit
from ugecy.registry import APPROVE_EDIT_REJECT, register_tool

# poll backoff: first delay, factor, max delay, overall cap (seconds). Tests shrink these.
POLL = {"first": 2.0, "factor": 1.5, "max": 10.0, "cap": 900.0}
_TERMINAL = {"completed", "failed"}
_RETENTION_DAYS = 7  # Higgsfield deletes outputs after 7 days; ingest copies them, otherwise the url dies
_tasks: set[asyncio.Task] = set()  # keep strong refs so background pollers are not garbage collected
_polling: set[str] = set()  # asset ids with a live poller (resume_media_jobs must not double-poll)
_PLACEHOLDER_URL = "https://example.invalid/chained-asset.png"  # estimate only; never submitted


async def _audit(action: str, status: str, detail: str, thread_id: str | None, tool_name: str) -> None:
    d = get_deps()
    await d.app.add_audit(AuditEntry(id=uuid4().hex, thread_id=thread_id, actor="agent", action=action, tool=tool_name,
                                     status=status, mode=d.modes.media, detail=detail[:500]))  # type: ignore[arg-type]


async def _save(asset: Asset) -> None:
    await get_deps().app.upsert_asset(asset)
    try:
        emit("asset.updated", asset=asset.model_dump(mode="json"))
    except (RuntimeError, KeyError):  # no stream writer: tests, or a poller outliving its run
        pass


def _merged_args(model: str, prompt: str, args: dict | None, chained: dict | None = None) -> dict:
    spec = next((m for m in get_deps().media.models() if m["endpoint_id"] == model), None)
    return {**(spec["defaults"] if spec else {}), **(args or {}), **(chained or {}), "prompt": prompt}


async def _chain_args(image_asset_id: str | None, reference_asset_ids: list[str] | None, *, estimate: bool = False) -> dict:
    """Completed asset ids -> provider URLs (image_url / image_urls). Raises ValueError with an agent-readable reason.
    estimate=True tolerates unresolved assets (the approval card still needs a price)."""
    d = get_deps()

    async def url_of(asset_id: str) -> str:
        a = await d.app.get_asset(asset_id)
        if a is None:
            raise ValueError(f"unknown asset {asset_id}")
        if a.status != "completed" or not a.url:
            raise ValueError(f"asset {asset_id} is {a.status}, not completed: wait for check_media_job")
        if a.kind != "image":
            raise ValueError(f"asset {asset_id} is a {a.kind}; only image assets can be chained as references")
        if d.media.mode == "live" and not a.url.startswith("http"):
            raise ValueError(f"asset {asset_id} has no public url the provider can fetch")
        return a.url

    out: dict = {}
    for key, ids in (("image_url", [image_asset_id] if image_asset_id else []), ("image_urls", reference_asset_ids or [])):
        urls = []
        for i in ids:
            try:
                urls.append(await url_of(i))
            except ValueError:
                if not estimate:
                    raise
                urls.append(_PLACEHOLDER_URL)
        if urls:
            out[key] = urls[0] if key == "image_url" else urls
    return out


async def estimate_for_approval(args: dict) -> float | None:
    """Called by the approval layer (02-04) with the pending generate_media args (works for any catalog model, chained or not)."""
    try:
        model = args["model"]
        chained = await _chain_args(args.get("image_asset_id"), args.get("reference_asset_ids"), estimate=True)
        return await get_deps().media.estimate(model, _merged_args(model, str(args.get("prompt", "")), args.get("args"), chained))
    except Exception:  # noqa: BLE001
        return None


def _expiry_note(out: dict[str, str]) -> str:
    exp = out.get("expires_at") or (datetime.now(UTC) + timedelta(days=_RETENTION_DAYS)).isoformat(timespec="seconds")
    return f"expires_at={exp} (provider urls are deleted after {_RETENTION_DAYS} days)"


async def _poll(asset_id: str, thread_id: str | None) -> None:
    d = get_deps()
    waited, delay, flaps = 0.0, POLL["first"], 0
    try:
        while waited < POLL["cap"]:
            asset = await d.app.get_asset(asset_id)
            if asset is None or asset.status in _TERMINAL or not asset.job_id:
                return
            try:
                job = await d.media.get(asset.job_id)
                flaps = 0
            except Exception:  # transient network / 5xx: keep the job alive, give up after 3 in a row
                flaps += 1
                if flaps >= 3:
                    raise
                await asyncio.sleep(delay)
                waited += delay
                continue
            if job.status in ("queued", "in_progress"):
                if job.status != asset.status:
                    await _save(asset.model_copy(update={"status": job.status}))
                await asyncio.sleep(delay)
                waited += delay
                delay = min(delay * POLL["factor"], POLL["max"])
                continue
            if job.status == "completed" and job.outputs:
                out = job.outputs[0]
                url = out["url"]
                if url.startswith("http"):  # data: URIs (mock) have nothing to ingest
                    try:
                        ing = await d.edge.media_ingest(asset_id, url, out["kind"])
                        url = ing.get("playback_url") or ing.get("url") or url
                        thumb = ing.get("thumbnail_url") or (url if out["kind"] == "image" else None)
                    except Exception as e:  # keep the provider URL; it dies in 7 days, so say so  # noqa: BLE001
                        await _audit("media_ingest", "error", f"{type(e).__name__}: ingest failed, provider url expires", thread_id, "generate_media")
                        thumb = url if out["kind"] == "image" else None
                else:
                    thumb = url
                await _save(asset.model_copy(update={"status": "completed", "url": url, "thumbnail_url": thumb}))
                await _audit("media_job", "ok", f"completed job {asset.job_id}; {_expiry_note(out)}", thread_id, "generate_media")
            else:
                await _save(asset.model_copy(update={"status": "failed"}))
                await _audit("media_job", "error", f"{job.status}: {job.error or 'no outputs'}", thread_id, "generate_media")
            return
        asset = await d.app.get_asset(asset_id)
        if asset and asset.status not in _TERMINAL:
            await _save(asset.model_copy(update={"status": "failed"}))
            await _audit("media_job", "error", "poll timed out", thread_id, "generate_media")
    except Exception as e:  # never let a background poller die silently  # noqa: BLE001
        asset = await d.app.get_asset(asset_id)
        if asset and asset.status not in _TERMINAL:
            await _save(asset.model_copy(update={"status": "failed"}))
        await _audit("media_job", "error", f"poller crashed: {type(e).__name__}", thread_id, "generate_media")
    finally:
        _polling.discard(asset_id)


def _spawn_poll(asset_id: str, thread_id: str | None) -> None:
    if asset_id in _polling:
        return
    _polling.add(asset_id)
    t = asyncio.create_task(_poll(asset_id, thread_id))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


async def resume_media_jobs() -> int:
    """Startup hook: re-poll every asset left queued/in_progress with a provider job id (container restarts lose pollers).
    Returns how many pollers were started."""
    n = 0
    for a in await get_deps().app.list_assets():
        if a.status in ("queued", "in_progress") and a.job_id and a.id not in _polling:
            _spawn_poll(a.id, a.thread_id)
            n += 1
    return n


class _EstimateIn(BaseModel):
    model: str
    args: dict | None = Field(default=None, description="generation args, include prompt")


class _GenerateIn(BaseModel):
    model: str = Field(description="endpoint_id from list_media_models")
    prompt: str
    kind: str = "video"
    args: dict | None = Field(default=None, description="extra model args (duration, aspect_ratio, resolution...)")
    image_asset_id: str | None = Field(default=None, description="completed image asset to animate; becomes image_url (Seedance/Kling/Wan image-to-video)")
    reference_asset_ids: list[str] | None = Field(default=None, description="completed image assets used as image_urls (Seedance reference-to-video)")
    brief_path: str | None = None


@tool
async def list_media_models(kind: str | None = None) -> str:
    """List available media generation models (image/video/audio) with defaults. Optional kind filter."""
    return json.dumps(get_deps().media.models(kind))


@tool(args_schema=_EstimateIn)
async def estimate_media_cost(model: str, args: dict | None = None) -> str:
    """Estimate USD cost of a media generation for a model endpoint_id and its args (include prompt)."""
    est = await get_deps().media.estimate(model, args or {})
    return json.dumps({"model": model, "estimated_usd": est})


@tool(args_schema=_GenerateIn)
async def generate_media(model: str, prompt: str, kind: str = "video", args: dict | None = None,
                         image_asset_id: str | None = None, reference_asset_ids: list[str] | None = None,
                         brief_path: str | None = None) -> str:
    """Generate an image/video/audio asset with a catalog model (costs money; needs approval).
    Returns the asset id and status; the file arrives asynchronously (use check_media_job).
    Videos for UGC should be 9:16. For image-to-video pass image_asset_id (a completed still); for
    reference-to-video pass reference_asset_ids. Optional brief_path points at the creative brief file."""
    d = get_deps()
    spec = next((m for m in d.media.models() if m["endpoint_id"] == model), None)
    if spec is None:
        return json.dumps({"error": f"unknown model {model!r}; call list_media_models"})
    thread_id = current_thread_id()
    try:
        full = _merged_args(model, prompt, args, await _chain_args(image_asset_id, reference_asset_ids))
    except ValueError as e:
        return json.dumps({"error": str(e)})
    missing = [r for r in spec.get("requires", []) if not full.get(r)]
    if missing:
        return json.dumps({"error": f"{model} needs {', '.join(missing)}: pass image_asset_id (or reference_asset_ids) of a completed still"})
    asset = Asset(id=f"asset_{uuid4().hex[:12]}", thread_id=thread_id, kind=spec["kind"], status="queued",
                  provider=d.media.name, model=model, prompt=prompt, mode=d.modes.media,
                  estimated_usd=await d.media.estimate(model, full))
    key = uuid4().hex  # server-generated; the provider dedupes retries on it
    try:
        job = await d.media.submit(model, full, idempotency_key=key)
    except Exception as e:  # noqa: BLE001
        await _audit("media_job", "error", f"submit failed: {type(e).__name__}: {e}", thread_id, "generate_media")
        return json.dumps({"error": f"submit failed: {e}"})
    asset = asset.model_copy(update={"job_id": job.job_id, "status": "queued" if job.status in ("queued", "in_progress") else job.status})  # type: ignore[arg-type]
    await _save(asset)
    await _audit("media_job", "ok", f"submitted {model} job={job.job_id} est={asset.estimated_usd} brief={brief_path or '-'}", thread_id, "generate_media")
    _spawn_poll(asset.id, thread_id)
    return json.dumps({"asset_id": asset.id, "status": asset.status, "kind": asset.kind, "mode": asset.mode,
                       "job_id": job.job_id, "estimated_usd": asset.estimated_usd})


@tool
async def check_media_job(asset_id: str) -> str:
    """Check the status of a media generation by asset id; includes url once completed."""
    asset = await get_deps().app.get_asset(asset_id)
    if asset is None:
        return json.dumps({"error": f"unknown asset {asset_id}"})
    return json.dumps({"asset_id": asset.id, "status": asset.status, "url": asset.url, "kind": asset.kind, "job_id": asset.job_id,
                       "model": asset.model, "estimated_usd": asset.estimated_usd, "mode": asset.mode})


register_tool(list_media_models, domain="media")
register_tool(estimate_media_cost, domain="media")
register_tool(generate_media, domain="media", interrupt=APPROVE_EDIT_REJECT, side_effect=True)
register_tool(check_media_job, domain="media")

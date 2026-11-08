"""Domain publishing tools. publish_post is irreversible: the operator approves each post; audited, AI-disclosure enforced."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from langchain_core.tools import tool

from ugecy.contracts import AuditEntry, ConnectedAccount, Post
from ugecy.deps import get_deps
from ugecy.events import current_thread_id
from ugecy.integrations.publishing.policy import is_ai_generated
from ugecy.integrations.unavailable import PUBLISH_OFF
from ugecy.registry import APPROVE_EDIT_REJECT, register_tool

CAPTION_LIMITS = {"tiktok": 2200, "instagram": 2200, "youtube": 5000, "facebook": 5000}


async def _audit(action: str, status: str, detail: str, thread_id: str | None) -> None:
    d = get_deps()
    await d.app.add_audit(AuditEntry(id=uuid4().hex, thread_id=thread_id, actor="agent", action=action, tool="publish_post",
                                     status=status, mode=d.modes.publishing, detail=detail[:500]))  # type: ignore[arg-type]


async def _accounts() -> list[ConnectedAccount]:
    return await get_deps().app.list_accounts()  # only accounts a real connection created; never seeded


async def run_publish_job(post_id: str) -> dict:
    """Publish a stored post. Idempotent: already-published posts are a no-op. Exposed at POST /jobs/publish."""
    d = get_deps()
    post = await d.app.get_post(post_id)
    if post is None:
        return {"status": "error", "error": f"unknown post {post_id}"}
    if post.status == "published":
        return {"status": "published", "external_url": post.external_url, "noop": True}
    asset = await d.app.get_asset(post.asset_id) if post.asset_id else None
    try:
        res = await d.publisher.publish(post, asset)
    except Exception as e:  # noqa: BLE001
        await d.app.upsert_post(post.model_copy(update={"status": "failed"}))
        await _audit("publish", "error", f"post {post_id}: {e}", post.thread_id)
        return {"status": "failed", "error": str(e)}
    await d.app.upsert_post(post.model_copy(update={"status": "published", "external_url": res.get("external_url")}))
    await _audit("publish", "ok", f"post {post_id} -> {res.get('external_url')}", post.thread_id)
    return {"status": "published", "external_url": res.get("external_url")}


@tool
async def list_connected_accounts() -> str:
    """List connected social accounts (id, platform, handle, mode) available for publishing."""
    accts = [a.model_dump() for a in await _accounts()]
    if accts:
        return json.dumps(accts)
    return json.dumps({"accounts": [], "note": "No social accounts connected. " + PUBLISH_OFF})


@tool
async def publish_post(account_id: str, asset_id: str, caption: str, ai_disclosure: bool,
                       publish_at: str | None = None) -> str:
    """Publish (or schedule, with an ISO publish_at in the future) a completed asset to a connected account.
    Irreversible, no approval step: only when the operator asked to post. ai_disclosure must be true for AI-generated media; the platform AI label is set from it."""
    d = get_deps()
    thread_id = current_thread_id()
    if d.publisher.mode == "off":
        await _audit("publish", "rejected", "publishing not connected", thread_id)
        return json.dumps({"error": PUBLISH_OFF})
    acct = next((a for a in await _accounts() if a.id == account_id), None)
    asset = await d.app.get_asset(asset_id)
    when: datetime | None = None
    if publish_at:
        try:
            when = datetime.fromisoformat(publish_at)
        except ValueError:
            return json.dumps({"error": f"publish_at is not ISO-8601: {publish_at!r}"})
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
    err = (
        f"unknown account {account_id}" if acct is None
        else f"unknown asset {asset_id}" if asset is None
        else f"asset not ready (status {asset.status})" if asset.status != "completed"
        else "ai_disclosure must be true for AI-generated media" if is_ai_generated(asset) and not ai_disclosure
        else f"caption too long for {acct.platform} ({len(caption)}>{CAPTION_LIMITS[acct.platform]})" if len(caption) > CAPTION_LIMITS[acct.platform]
        else None
    )
    if err:
        await _audit("publish", "rejected", err, thread_id)
        return json.dumps({"error": err})
    future = when is not None and when > datetime.now(UTC)
    edge = d.settings.internal_mode == "edge"
    post = Post(id=f"post_{uuid4().hex[:12]}", thread_id=thread_id, account_id=account_id, asset_id=asset_id, caption=caption,
                ai_disclosure=ai_disclosure, status="scheduled" if future else "draft", mode=d.modes.publishing,
                publish_at=when.isoformat() if when else None)
    await d.app.upsert_post(post)
    if future and edge:
        wf = await d.edge.schedule_publish(post.id, post.publish_at)
        await _audit("publish", "pending", f"scheduled post {post.id} for {post.publish_at} workflow={wf}", thread_id)
        return json.dumps({"post_id": post.id, "status": "scheduled", "publish_at": post.publish_at})
    res = await run_publish_job(post.id)
    note = "scheduling needs the edge workflow; published immediately in local mode" if future else None
    return json.dumps({"post_id": post.id, **res, **({"note": note} if note else {})})


@tool
async def get_post_status(post_id: str) -> str:
    """Get a post's status and external URL by post id."""
    post = await get_deps().app.get_post(post_id)
    if post is None:
        return json.dumps({"error": f"unknown post {post_id}"})
    return json.dumps({"post_id": post.id, "status": post.status, "external_url": post.external_url, "publish_at": post.publish_at})


register_tool(list_connected_accounts, domain="publishing")
register_tool(publish_post, domain="publishing", interrupt=APPROVE_EDIT_REJECT, side_effect=True)  # approvals: money and posting
register_tool(get_post_status, domain="publishing")

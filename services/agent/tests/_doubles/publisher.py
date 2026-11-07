"""Mock publisher: never touches a network. Enforces the AI-disclosure rule (FEATURES.md 3.2)."""
from __future__ import annotations

from typing import Any

from ugecy.contracts import Asset, Post
from ugecy.deps import get_deps
from ugecy.integrations.publishing.policy import DisclosureRequired, is_ai_generated


class MockPublisher:
    name = "mock-publisher"
    mode = "mock"

    def __init__(self, settings: Any = None):
        self._settings = settings

    async def publish(self, post: Post, asset: Asset | None) -> dict[str, Any]:
        if is_ai_generated(asset) and not post.ai_disclosure:
            raise DisclosureRequired("AI-generated media must be published with ai_disclosure=true")
        accounts = await get_deps().app.list_accounts()
        platform = next((a.platform for a in accounts if a.id == post.account_id), "unknown")
        return {"status": "published", "external_url": f"https://example.com/mock/{platform}/{post.id}"}

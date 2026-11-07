"""AI-disclosure rule (FEATURES.md 3.2), shared by the publish tool and any publisher."""
from __future__ import annotations

from ugecy.contracts import Asset


class DisclosureRequired(ValueError):
    pass


def is_ai_generated(asset: Asset | None) -> bool:
    return asset is not None and asset.provider != "upload"

"""Test providers that stand in for connected ones."""
from __future__ import annotations

from typing import Any


def install_fakes(deps: Any, *, research: bool = True, media: bool = True, device: bool = True,
                  publisher: bool = True, analytics: bool = True) -> Any:
    """Swap the chosen providers on a built Deps for fakes and report them as live."""
    from tests._doubles.analytics import FakeAnalytics
    from tests._doubles.device import FakeDeviceProvider
    from tests._doubles.media import FakeMediaProvider
    from tests._doubles.publisher import FakePublisher
    from tests._doubles.research import FakeResearchProvider

    s = deps.settings
    if research:
        deps.research, deps.modes.research = FakeResearchProvider(s), "live"
    if media:
        deps.media, deps.modes.media = FakeMediaProvider(), "live"
    if device:
        deps.device, deps.modes.device = FakeDeviceProvider(), "live"
    if publisher:
        deps.publisher, deps.modes.publishing = FakePublisher(s), "live"
    if analytics:
        deps.analytics = FakeAnalytics(s)
    return deps

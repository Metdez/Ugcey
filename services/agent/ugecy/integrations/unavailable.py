"""Off providers: what a capability does when it is not connected. Never fabricates data (phase 06)."""
from __future__ import annotations

from typing import Any

from ugecy.contracts import DeviceInfo, Mode, Post
from ugecy.integrations.media.catalog import catalog_models
from ugecy.interfaces import MediaJob

MEDIA_OFF = "Video generation not connected: set its API key Worker secret (README, Secrets)"
DEVICE_OFF = "No iPhone connected: connect it in the Device tab"
PUBLISH_OFF = ("Direct API publishing isn't connected; publish from the iPhone via the device-operator "
               "(with approval)")
ANALYTICS_OFF = "No analytics source connected; have the device-operator read metrics on the iPhone with device_observe"
STORAGE_OFF = "Dropbox not connected: open Accounts in the sidebar and connect Dropbox"
SEARCH_OFF = ("Web research not connected: add its API key Worker secret (README, Secrets). Use deep_search, "
              "deep_research or fetch_page meanwhile.")
TAVILY_OFF = ("Deep research not connected: add its API key Worker secret (README, Secrets). Use web_search and "
              "fetch_page meanwhile.")


class NotConnected(RuntimeError):
    """A capability is off; str(e) tells the operator exactly what to connect."""


class OffMediaProvider:
    name = "higgsfield"
    mode: Mode = "off"

    def __init__(self, settings: Any = None) -> None:
        self.settings = settings

    def models(self, kind: str | None = None) -> list[dict[str, Any]]:
        return catalog_models(kind)  # the real catalog stays listable

    async def estimate(self, model: str, args: dict[str, Any]) -> float | None:
        raise NotConnected(MEDIA_OFF)

    async def submit(self, model: str, args: dict[str, Any], *, idempotency_key: str) -> MediaJob:
        raise NotConnected(MEDIA_OFF)

    async def get(self, job_id: str) -> MediaJob:
        raise NotConnected(MEDIA_OFF)

    async def upload(self, data: bytes, content_type: str) -> str:
        raise NotConnected(MEDIA_OFF)


class OffDeviceProvider:
    name = "glasshand"
    mode: Mode = "off"

    def __init__(self, settings: Any = None) -> None:
        self.settings = settings

    async def list_devices(self) -> list[DeviceInfo]:
        return []

    async def screenshot(self, device_id: str) -> bytes:
        raise NotConnected(DEVICE_OFF)

    async def describe(self, device_id: str) -> str:
        raise NotConnected(DEVICE_OFF)

    async def send(self, device_id: str, action: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        raise NotConnected(DEVICE_OFF)

    async def observe(self, device_id: str) -> dict[str, Any] | None:
        raise NotConnected(DEVICE_OFF)


class OffPublisher:
    name = "none"
    mode: Mode = "off"

    def __init__(self, settings: Any = None) -> None:
        self.settings = settings

    async def publish(self, post: Post, asset: Any) -> dict[str, Any]:
        raise NotConnected(PUBLISH_OFF)


class OffAnalytics:
    name = "none"
    mode: Mode = "off"

    def __init__(self, settings: Any = None) -> None:
        self.settings = settings

    async def post_metrics(self, posts: list[Post]) -> list[dict[str, Any]]:
        raise NotConnected(ANALYTICS_OFF)

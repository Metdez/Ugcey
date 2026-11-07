import httpx
import pytest

from tests._fakes_04_02 import FakeVision, gateway, vision_json
from ugecy.integrations.device.auto import AutoDeviceProvider
from ugecy.integrations.unavailable import NotConnected
from ugecy.settings import Settings

EDGE = Settings(internal_mode="edge")


class Clock:
    t = 100.0

    def __call__(self):
        return self.t


def auto(handler, clock):
    return AutoDeviceProvider(EDGE, transport=httpx.MockTransport(handler), clock=clock, vision_model=FakeVision(vision_json()))


async def test_connected_uses_glasshand_and_dynamic_mode():
    a = auto(gateway(status={"connected": True, "selected_rental_id": "r1"}), Clock())
    assert (a.name, a.mode) == ("glasshand", "off")
    assert [d.id for d in await a.list_devices()] == ["r1"]
    assert (a.name, a.mode) == ("glasshand", "live")
    assert (await a.send("r1", {"type": "home"}, idempotency_key="k"))["ok"]


async def test_disconnected_and_unreachable_are_off_without_mock():
    for status in ({"connected": False, "selected_rental_id": None}, None):
        a = auto(gateway(status=status), Clock())
        assert await a.list_devices() == []
        assert a.mode == "off"
        with pytest.raises(NotConnected, match="No iPhone connected"):
            await a.describe("anything")
        with pytest.raises(NotConnected):
            await a.send("anything", {"type": "home"}, idempotency_key="k")


async def test_status_cache_expiry():
    seen, clock = [], Clock()
    state = {"connected": False, "selected_rental_id": None}
    a = auto(gateway(status=state, seen=seen), clock)

    def hits():
        return sum(r.url.path == "/_ugecy/status" for r in seen)

    await a.list_devices()
    state.update(connected=True, selected_rental_id="r1")
    clock.t += 14
    await a.list_devices()
    assert hits() == 1 and a.mode == "off"  # cached
    clock.t += 2
    assert [d.id for d in await a.list_devices()] == ["r1"]
    assert hits() == 2 and a.mode == "live"


async def test_live_rental_not_ready_is_off():
    a = auto(gateway(status={"connected": True, "selected_rental_id": "r2"}), Clock())
    assert await a.list_devices() == []
    assert a.mode == "off"


async def test_local_mode_needs_env_token():
    s = Settings(internal_mode="local")
    assert await AutoDeviceProvider(s).list_devices() == [] and AutoDeviceProvider(s).mode == "off"
    s2 = Settings(internal_mode="local", GLASSHAND_TOKEN="t", GLASSHAND_RENTAL_ID="r1")
    a = AutoDeviceProvider(s2, transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    assert await a.list_devices() == []  # api 500 -> off, no raise

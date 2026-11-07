import httpx

from tests._fakes_04_02 import FakeVision, gateway, vision_json
from ugecy.integrations.device.auto import AutoDeviceProvider
from ugecy.integrations.device.mock import DEVICE_ID
from ugecy.settings import Settings

EDGE = Settings(internal_mode="edge")


class Clock:
    t = 100.0

    def __call__(self):
        return self.t


def auto(handler, clock):
    return AutoDeviceProvider(EDGE, transport=httpx.MockTransport(handler), clock=clock, vision_model=FakeVision(vision_json()))


async def test_connected_uses_glasshand_and_dynamic_name():
    a = auto(gateway(status={"connected": True, "selected_rental_id": "r1"}), Clock())
    assert (a.name, a.mode) == ("mock-iphone", "mock")
    assert [d.id for d in await a.list_devices()] == ["r1"]
    assert (a.name, a.mode) == ("glasshand", "live")
    assert (await a.send("r1", {"type": "home"}, idempotency_key="k"))["ok"]


async def test_disconnected_and_unreachable_fall_back_without_raising():
    for status in ({"connected": False, "selected_rental_id": None}, None):
        a = auto(gateway(status=status), Clock())
        assert [d.id for d in await a.list_devices()] == [DEVICE_ID]
        assert a.mode == "mock"
        assert "Tappable" in await a.describe(DEVICE_ID)


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
    assert hits() == 1 and a.mode == "mock"  # cached
    clock.t += 2
    assert [d.id for d in await a.list_devices()] == ["r1"]
    assert hits() == 2 and a.mode == "live"


async def test_live_rental_not_ready_falls_back():
    a = auto(gateway(status={"connected": True, "selected_rental_id": "r2"}), Clock())
    assert [d.id for d in await a.list_devices()] == [DEVICE_ID]
    assert a.mode == "mock"


async def test_local_mode_needs_env_token():
    s = Settings(internal_mode="local")
    assert await AutoDeviceProvider(s).list_devices() and AutoDeviceProvider(s).mode == "mock"
    s2 = Settings(internal_mode="local", GLASSHAND_TOKEN="t", GLASSHAND_RENTAL_ID="r1")
    a = AutoDeviceProvider(s2, transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    assert [d.id for d in await a.list_devices()] == [DEVICE_ID]  # api 500 -> fallback, no raise

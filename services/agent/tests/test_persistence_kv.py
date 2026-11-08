
async def test_edge_kv_get_follows_pages():
    import base64
    import json

    import httpx

    from ugecy.persistence.kv import EdgeKV
    from ugecy.settings import Settings

    pages = {"": ({"a": b"1", "b": b"2"}, "b"), "b": ({"c": b"3"}, None)}

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        items, nxt = pages[body.get("after", "")]
        return httpx.Response(200, json={"items": [{"key": k, "value_b64": base64.b64encode(v).decode()}
                                                   for k, v in items.items()], "next": nxt})

    kv = EdgeKV(Settings(internal_mode="edge"))
    kv._http = httpx.AsyncClient(base_url="http://state.internal", transport=httpx.MockTransport(handler))
    assert await kv.get("ns", "") == {"a": b"1", "b": b"2", "c": b"3"}

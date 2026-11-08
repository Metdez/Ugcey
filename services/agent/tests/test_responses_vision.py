import json
from types import SimpleNamespace

import httpx

from ugecy.llm.responses_vision import ResponsesVision, output_text, to_responses_input
from ugecy.settings import Settings

MSG = [{"role": "user", "content": [{"type": "text", "text": "read"},
                                     {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AA"}}]}]


def test_to_responses_input_maps_text_and_image():
    out = to_responses_input(MSG)
    assert out[0]["content"] == [{"type": "input_text", "text": "read"},
                                 {"type": "input_image", "image_url": "data:image/jpeg;base64,AA"}]


def test_output_text_reads_message_parts():
    assert output_text({"output": [{"type": "message", "content": [{"type": "output_text", "text": "{}"}]}]}) == "{}"


async def test_edge_call_and_fallback():
    seen = {}

    def ok(req: httpx.Request) -> httpx.Response:
        seen["url"], seen["body"] = str(req.url), json.loads(req.content)
        return httpx.Response(200, json={"output_text": '{"elements":[]}'})

    v = ResponsesVision(Settings(internal_mode="edge"), "openai/gpt-6-luna", transport=httpx.MockTransport(ok))
    assert (await v.ainvoke(MSG)).content == '{"elements":[]}'
    assert seen["url"] == "http://llm.internal/v1/responses" and seen["body"]["model"] == "openai/gpt-6-luna"

    class Fallback:
        async def ainvoke(self, messages):
            return SimpleNamespace(content="fallback")

    bad = ResponsesVision(Settings(internal_mode="edge"), "openai/gpt-6-luna", fallback=Fallback(),
                          transport=httpx.MockTransport(lambda r: httpx.Response(402, json={})))
    assert (await bad.ainvoke(MSG)).content == "fallback"

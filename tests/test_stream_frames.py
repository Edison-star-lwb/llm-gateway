from gateway import mock
from gateway.registry import Route
from gateway.schemas import ChatRequest
from gateway.streaming import stream_events


async def test_stream_events_frames_are_sse_shaped(events, monkeypatch):
    route = Route(provider="qwen", upstream_model="qwen-plus")
    req = ChatRequest(message="深圳天气怎么样", model="qwen-plus")
    chunks = [c async for c in stream_events(route, req, "alice")]
    assert len(chunks) > 3
    assert all(c.startswith("data: ") and c.endswith("\n\n") for c in chunks)
    assert chunks[-1] == "data: [DONE]\n\n"
    assert events.count("upstream_call") == 1
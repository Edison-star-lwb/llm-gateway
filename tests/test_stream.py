from gateway import mock


def test_stream_sse_shape(client, headers):
    resp = client.post("/chat/stream", headers=headers,
                       json={"message": "深圳天气怎么样", "model": "qwen-plus"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    lines = [ln for ln in resp.text.splitlines() if ln]
    assert len(lines) > 3
    assert all(ln.startswith("data: ") for ln in lines)
    assert lines[-1] == "data: [DONE]"


def test_retry_recovers_after_two_failures(client, headers, events, monkeypatch):
    monkeypatch.setattr(mock, "_FAIL_TRIES", 0)
    monkeypatch.setenv("MOCK_FAIL_FIRST", "2")
    resp = client.post("/chat/stream", headers=headers,
                       json={"message": "重试测试", "model": "qwen-plus"})
    assert resp.status_code == 200
    assert events.count("upstream_call") == 3
    assert events.count("upstream_retry") == 2
    assert "data: [DONE]" in resp.text
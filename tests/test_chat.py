import pytest


def test_unknown_model_lists_supported(client, headers):
    resp = client.post("/chat", headers=headers,
                       json={"message": "hi", "model": "gpt-4o"})
    assert resp.status_code == 400
    data = resp.json()
    assert data["error"] == "unknown_model"
    assert len(data["supported"]) == 4


@pytest.mark.parametrize("bad", [{"temperature": 99}, {"message": ""}])
def test_field_validation_returns_422(client, headers, bad):
    payload = {"message": "hi", "model": "qwen-plus"}
    payload.update(bad)
    resp = client.post("/chat", headers=headers, json=payload)
    assert resp.status_code == 422

def test_unknown_model_returns_400(client, headers):
    resp = client.post("/chat", headers=headers, json={"message": "hi", "model": "gpt-99"})
    assert resp.status_code == 400
    assert "unknown_model" in resp.json()["error"]
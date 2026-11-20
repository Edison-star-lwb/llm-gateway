def test_missing_key_is_401(client):
    resp = client.post("/chat", json={"message": "hi"})
    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid_api_key"
    assert "sk-" not in resp.text


def test_wrong_key_is_401(client):
    resp = client.post("/chat", headers={"X-API-Key": "gw-wrong-999"},
                       json={"message": "hi"})
    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid_api_key"
    assert "gw-dev-001" not in resp.text
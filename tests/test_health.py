def test_health_is_open_and_reports_version(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data
    # 这条保护 §8 的 HEALTHCHECK：容器健康检查靠 status=ok 判断，改这个键名会让容器 unhealthy
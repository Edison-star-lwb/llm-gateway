import pytest
import logging
from fastapi.testclient import TestClient

from gateway.main import app

UPSTREAM_VARS = ("DEEPSEEK_API_KEY", "QWEN_API_KEY")


@pytest.fixture
def client(monkeypatch):
    return TestClient(app)


@pytest.fixture
def headers():
    return {"X-API-Key": "gw-dev-001"}


@pytest.fixture(autouse=True)
def hermetic_env(monkeypatch):
    monkeypatch.setenv("GATEWAY_ALLOWED_KEYS", "gw-dev-001:alice")
    monkeypatch.setenv("MOCK_LLM", "1")

    for name in UPSTREAM_VARS:
        monkeypatch.delenv(name, raising=False)

@pytest.fixture
def events():
    seen = []

    class _Capture(logging.Handler):
        def emit(self, record):
            seen.append(getattr(record, "event", None))

    handler = _Capture()
    handler.setLevel(logging.INFO)
    log = logging.getLogger("gateway")
    log.addHandler(handler)
    try:
        yield seen
    finally:
        log.removeHandler(handler)
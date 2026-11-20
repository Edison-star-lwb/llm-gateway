import secrets

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from gateway.config import load_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_authorization_header = APIKeyHeader(name="Authorization", auto_error=False)
def _from_bearer(authorization: str | None) -> str:
    if not authorization:
        return ""
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return ""
async def require_api_key(api_key: str | None = Depends(_api_key_header),
                          authorization: str | None = Depends(_authorization_header)) -> str:
    """返回调用方标签。挂 /chat 和 /chat/stream，绝不挂 /health。"""
    keys = load_settings().api_keys
    if not keys:
        raise HTTPException(500, {
            "error": "gateway_not_configured",
            "detail": "GATEWAY_ALLOWED_KEYS 未配置",
        })
    supplied = (api_key or "").strip() or _from_bearer(authorization)
    if supplied:
        for key, label in keys.items():
            if secrets.compare_digest(supplied, key):
                return label
    raise HTTPException(401, {"error": "invalid_api_key"})
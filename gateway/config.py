import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

class MissingConfig(RuntimeError):
    """配置缺失或格式不对。刻意区别于业务异常：它不该被重试。"""
    pass

def _num_env(name: str, default, cast):
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return cast(raw)
    except ValueError:
        raise MissingConfig(f"环境变量 {name} 需要数字，实际收到 {raw!r}") from None


def _int_env(name: str, default: int) -> int:
    return _num_env(name, default, int)


def _float_env(name: str, default: float) -> float:
    return _num_env(name, default, float)

def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    raise MissingConfig(f"环境变量 {name} 需要 0/1，实际收到 {raw!r}")

def _parse_keys(raw: str) -> dict[str, str]:
    keys: dict[str, str] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise MissingConfig("GATEWAY_ALLOWED_KEYS 格式应为 key:label,key:label")
        key, label = item.split(":", 1)
        keys[key.strip()] = label.strip()
    return keys

@dataclass(frozen=True)
class Settings:
    api_keys: dict[str, str]
    default_model: str
    max_concurrency: int
    upstream_timeout: float
    mock_llm: bool

def load_settings() -> Settings:

    return Settings(
    api_keys=_parse_keys(os.getenv("GATEWAY_ALLOWED_KEYS", "")),
    default_model=os.getenv("GATEWAY_DEFAULT_MODEL", "deepseek-chat"),
    max_concurrency=_int_env("GATEWAY_MAX_CONCURRENCY", 8),
    upstream_timeout=_float_env("GATEWAY_UPSTREAM_TIMEOUT", 30),
    mock_llm=_bool_env("MOCK_LLM", False),
)
import os
from dataclasses import dataclass

from openai import AsyncOpenAI

from gateway.config import MissingConfig, load_settings


@dataclass(frozen=True)
class Route:
    provider: str
    upstream_model: str


ROUTES: dict[str, Route] = {
    "deepseek-chat": Route("deepseek", "deepseek-chat"),
    "deepseek-reasoner": Route("deepseek", "deepseek-reasoner"),
    "qwen-plus": Route("qwen", "qwen-plus"),
    "qwen-turbo": Route("qwen", "qwen-turbo"),
}

PROVIDERS = {
    "deepseek": ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    "qwen": ("QWEN_API_KEY", "QWEN_BASE_URL",
             "https://dashscope.aliyuncs.com/compatible-mode/v1"),
}

_clients: dict[str, AsyncOpenAI] = {}


def get_client(provider: str) -> AsyncOpenAI:
    if provider in _clients:
        return _clients[provider]
    key_var, url_var, url_default = PROVIDERS[provider]
    api_key = os.getenv(key_var, "").strip()
    if not api_key:
        raise MissingConfig(f"缺少环境变量 {key_var}（provider={provider}）")
    s = load_settings()
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=os.getenv(url_var, url_default),
        timeout=s.upstream_timeout,
        max_retries=0,
    )
    _clients[provider] = client
    return client
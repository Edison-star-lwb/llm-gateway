import os
from openai import APIConnectionError, RateLimitError
import asyncio
from types import SimpleNamespace

_FAKE = "深圳今天多云，气温 22 到 27 度，风向东南，风力二级，降水概率 30%，建议带一把薄伞，上午适合户外，午后有短时阵雨，傍晚转晴，夜里 18 度，体感舒适，空气湿度 65%，紫外线中等，防晒不必，跑步可以，穿衣建议长袖加薄外套，出行建议错峰，地铁沿线畅通，深圳湾边人较多，拍照趁早。"


def _chunk(text, usage=None):
    """造一个形状贴近 openai ChatCompletionChunk 的对象。"""
    delta = SimpleNamespace(content=text, reasoning_content=None)
    return SimpleNamespace(
        choices=[] if (text is None and usage is not None) else [SimpleNamespace(index=0, delta=delta)],
        usage=usage,
    )


async def stream_fake(prompt, **kwargs):
    break_after = int(os.getenv("MOCK_BREAK_AFTER", "0") or 0)   # 新增
    yield _chunk(None)
    n = 0                                                        # 新增
    for piece in _FAKE.split("，"):
        await asyncio.sleep(0.05)
        n += 1                                                   # 新增
        if break_after and n > break_after:                      # 新增
            raise _connection_died()                             # 新增
        yield _chunk(piece + "，")
    yield _chunk(None, usage=SimpleNamespace(
        prompt_tokens=len(prompt),
        completion_tokens=len(_FAKE),
        total_tokens=len(prompt) + len(_FAKE),
    ))


_FAIL_TRIES = 0


def _rate_limit_error():
    fake_response = SimpleNamespace(request=None, status_code=429, headers={})
    return RateLimitError("mock: 上游说太频繁了", response=fake_response, body=None)

def _connection_died():
    return APIConnectionError(request=None)

async def open_fake_stream(prompt: str):
    global _FAIL_TRIES
    limit = int(os.getenv("MOCK_FAIL_FIRST", "0") or 0)
    if limit and _FAIL_TRIES < limit:
        _FAIL_TRIES += 1
        raise _rate_limit_error()
    _FAIL_TRIES = 0
    return stream_fake(prompt)   
import asyncio
import json
import time
import traceback
from gateway.billing import estimate_tokens
from gateway.config import load_settings
from gateway.logging_setup import emit, emit_error, setup
from gateway.mock import stream_fake
from gateway.registry import get_client
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter
from gateway.mock import open_fake_stream

def sse(obj) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def to_messages(user_text: str) -> list[dict]:
    return [
        {"role": "system", "content": "你是一个简洁的助手"},
        {"role": "user", "content": user_text},
    ]
_SEM: asyncio.Semaphore | None = None


def semaphore() -> asyncio.Semaphore:
    global _SEM
    if _SEM is None:
        _SEM = asyncio.Semaphore(load_settings().max_concurrency)
    return _SEM

log = setup()
RETRYABLE = (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)


def _note_attempt(retry_state):
    exc = retry_state.outcome.exception()
    emit(log, "upstream_retry", attempt=retry_state.attempt_number,
         detail=f"{type(exc).__name__}，{retry_state.upcoming_sleep} 秒后重试")


@retry(stop=stop_after_attempt(3),
       wait=wait_exponential_jitter(initial=0.3, max=3),
       retry=retry_if_exception_type(RETRYABLE),
       before_sleep=_note_attempt,
       reraise=True)
async def open_stream(route, req):
    emit(log, "upstream_call", model=route.upstream_model)
    if load_settings().mock_llm:
        return await open_fake_stream(req.message)
    client = get_client(route.provider)
    return await client.chat.completions.create(
        model=route.upstream_model,
        messages=to_messages(req.message),
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        stream=True,
        stream_options={"include_usage": True},
    )


async def stream_events(route, req, caller):
    started = time.perf_counter()
    status = "ok"
    usage_seen = None
    buf: list[str] = []
    emitted = 0
    
    try:
        async with semaphore():
            stream = await open_stream(route, req)
            async for chunk in stream:
                if getattr(chunk, "usage", None):
                    usage_seen = chunk.usage
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                piece = getattr(delta, "content", None)
                if piece is None:
                    continue

                emitted += 1
                buf.append(piece)
                yield sse({"token": piece})

    except Exception as exc:
        status = type(exc).__name__
        emit_error(log, "upstream_error", exc, caller=caller, model=route.upstream_model)
        yield sse({"error": "upstream_stream_interrupted",
                   "detail": type(exc).__name__,
                   "partial_tokens": emitted})

    if usage_seen is not None:
        usage_row = {"prompt_tokens": usage_seen.prompt_tokens,
                    "completion_tokens": usage_seen.completion_tokens,
                    "total_tokens": usage_seen.total_tokens,
                    "source": "upstream"}
    else:
        answer = "".join(buf)
        comp, comp_src = estimate_tokens(answer)
        prompt, _src = estimate_tokens(req.message)
        usage_row = {"prompt_tokens": prompt, "completion_tokens": comp,
                    "total_tokens": prompt + comp, "source": comp_src}
    yield sse({"usage": usage_row})

    emit(log, "request_out", caller=caller, model=route.upstream_model,
         latency_ms=int((time.perf_counter() - started) * 1000),
         status=status, usage=usage_row)

    yield "data: [DONE]\n\n"
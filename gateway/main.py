import time
import uuid
import json
from typing import Annotated
from pathlib import Path
from gateway import metrics
from gateway.billing import append_ledger
from fastapi import FastAPI, HTTPException, Request,Depends
from fastapi.responses import JSONResponse,StreamingResponse

from gateway.config import MissingConfig, load_settings
from gateway.registry import ROUTES, get_client
from gateway.schemas import (ChatMessage, ChatRequest, ChatResponse, CompletionChoice,
                             CompletionRequest, CompletionResponse, CompletionUsage, Usage)
from gateway.auth import require_api_key
from gateway.logging_setup import emit, new_request_id, request_id_var, setup
from gateway.streaming import stream_events
VERSION = "0.1.0"
log = setup()
app = FastAPI(title="LLM 统一网关", version=VERSION)


@app.exception_handler(HTTPException)
async def http_exc_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code,
                        content={"error": "request_failed", "detail": exc.detail})


@app.exception_handler(MissingConfig)
async def missing_config_handler(request: Request, exc: MissingConfig):
    return JSONResponse(status_code=500,
                        content={"error": "gateway_not_configured", "detail": str(exc)})

@app.middleware("http")
async def request_id_mw(request: Request, call_next):
    rid = new_request_id()
    token = request_id_var.set(rid)
    metrics.inc_request()
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    caller = request.headers.get("X-API-Key", "unknown")
    metrics.dec_request(response.status_code, caller)
    response.headers["X-Request-Id"] = rid
    return response

@app.get("/health")
async def health():
    return {"status": "ok", "version": VERSION, "models": len(ROUTES)}


@app.get("/metrics")
async def metrics_endpoint():
    return metrics.snapshot()

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, caller: str = Depends(require_api_key)):
    name = req.model or load_settings().default_model
    emit(log, "request_in", caller=caller, model=name)
    route = ROUTES.get(name)
    if route is None:
        append_ledger({"caller": caller, "model": name, "prompt_tokens": 0,
                "completion_tokens": 0, "total_tokens": 0,
                "usage_source": "none", "latency_ms": 0,
                "status": "unknown_model"})
        emit(log, "request_out", caller=caller, model=name, status="unknown_model")
        raise HTTPException(400, {
            "error": "unknown_model",
            "detail": f"model={name} 不在路由表",
            "supported": sorted(ROUTES),
        })

    client = get_client(route.provider)
    messages = [
        {"role": "system", "content": "你是一个简洁的助手"},
        {"role": "user", "content": req.message},
    ]

    started = time.perf_counter()
    async with semaphore():
        resp = await client.chat.completions.create(
            model=route.upstream_model,
            messages=messages,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
    latency_ms = int((time.perf_counter() - started) * 1000)
    if resp.usage is not None:
        pt = resp.usage.prompt_tokens or 0
        ct = resp.usage.completion_tokens or 0
        usage = Usage(prompt_tokens=pt, completion_tokens=ct,
                      total_tokens=resp.usage.total_tokens or (pt + ct),
                      source="upstream")
    else:
        usage = Usage(prompt_tokens=0, completion_tokens=0,
                      total_tokens=0, source="fallback")

    append_ledger({"caller": caller, "model": name,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "usage_source": usage.source,
                "latency_ms": latency_ms, "status": "ok"})
    emit(log, "request_out", caller=caller, model=name, latency_ms=latency_ms,
    status="ok",
    usage={"prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens, "source": usage.source})
    return ChatResponse(
        request_id=uuid.uuid4().hex,
        model=name,
        content=resp.choices[0].message.content or "",
        usage=usage,
        latency_ms=latency_ms,
    )

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, caller: str = Depends(require_api_key)):
    name = req.model or load_settings().default_model
    emit(log, "request_in", caller=caller, model=name)
    route = ROUTES.get(name)
    if route is None:
        raise HTTPException(400, {
            "error": "unknown_model",
            "detail": f"model={name} 不在路由表",
            "supported": sorted(ROUTES),
        })
    return StreamingResponse(
        stream_events(route, req, caller),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/v1/chat/completions")
async def chat_completions(req: CompletionRequest,
                           caller: Annotated[str, Depends(require_api_key)]):
    name = req.model
    emit(log, "request_in", caller=caller, model=name)
    route = ROUTES.get(name)
    if route is None:
        emit(log, "request_out", caller=caller, model=name, status="unknown_model")
        raise HTTPException(400, {
            "error": "unknown_model",
            "detail": f"model={name} 不在路由表",
            "supported": sorted(ROUTES),
        })

    client = get_client(route.provider)
    kwargs = {}
    if req.temperature is not None:
        kwargs["temperature"] = req.temperature
    if req.max_tokens is not None:
        kwargs["max_tokens"] = req.max_tokens

    started = time.perf_counter()
    resp = await client.chat.completions.create(
        model=route.upstream_model,
        messages=[m.model_dump() for m in req.messages],
        stream=False,
        **kwargs,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    if resp.usage is not None:
        pt = resp.usage.prompt_tokens or 0
        ct = resp.usage.completion_tokens or 0
        tt = resp.usage.total_tokens or (pt + ct)
        src = "upstream"
    else:
        pt = ct = tt = 0
        src = "fallback"

    rid = request_id_var.get()
    append_ledger({"caller": caller, "model": name, "request_id": rid,
                   "prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt,
                   "usage_source": src, "latency_ms": latency_ms, "status": "ok"})
    emit(log, "request_out", caller=caller, model=name, latency_ms=latency_ms,
         status="ok", usage={"prompt_tokens": pt, "completion_tokens": ct,
                             "total_tokens": tt, "source": src})

    choice = resp.choices[0]
    return CompletionResponse(
        id="chatcmpl-" + rid,
        object="chat.completion",
        created=int(time.time()),
        model=name,
        choices=[CompletionChoice(index=0,
                                  message=ChatMessage(role="assistant",
                                                      content=choice.message.content or ""),
                                  finish_reason=choice.finish_reason)],
        usage=CompletionUsage(prompt_tokens=pt, completion_tokens=ct, total_tokens=tt),
    )

@app.get("/v1/models")
async def list_models():
    data = [{"id": name, "object": "model", "owned_by": "TODO"}
            for name in sorted(ROUTES)]
    return {"object": "list", "data": data}


@app.get("/usage")
async def usage(caller: Annotated[str, Depends(require_api_key)]):
    p = Path("data/ledger.jsonl")
    if not p.exists():
        return {"by_caller": {}}
    totals: dict[str, dict[str, int]] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        who = row.get("caller", "?")
        bucket = totals.setdefault(who, {"calls": 0, "total_tokens": 0, "errors": 0})
        bucket["calls"] += 1
        bucket["total_tokens"] += row.get("total_tokens", 0)
        if row.get("status") != "ok":
            bucket["errors"] += 1
    return {"by_caller": totals}
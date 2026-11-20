import json
import logging
import os
import traceback as tb
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "request_id": request_id_var.get(),
            "event": getattr(record, "event", "log"),
            "caller": getattr(record, "caller", None),
            "model": getattr(record, "model", None),
            "latency_ms": getattr(record, "latency_ms", None),
            "status": getattr(record, "status", None),
            "attempt": getattr(record, "attempt", None),
            "usage": getattr(record, "usage", None),
            "detail": record.getMessage(),
        }
        if record.exc_info:
            payload["traceback"] = "".join(tb.format_exception(*record.exc_info))
        return json.dumps({k: v for k, v in payload.items() if v is not None},
                          ensure_ascii=False)


def setup() -> logging.Logger:
    log = logging.getLogger("gateway")
    log.setLevel(logging.INFO)
    if not log.handlers:
        log.addHandler(logging.StreamHandler())
        path = os.getenv("GATEWAY_LOG_FILE", "").strip()
        if path:
            log.addHandler(logging.FileHandler(path, encoding="utf-8"))
        for h in log.handlers:
            h.setFormatter(JsonFormatter())
    log.propagate = False
    return log


def new_request_id() -> str:
    return uuid.uuid4().hex


def emit(log, event, detail="", **fields):
    log.info(detail or event, extra={"event": event, **fields})


def emit_error(log, event, exc, detail="", **fields):
    log.error(detail or event, extra={"event": event, **fields}, exc_info=exc)
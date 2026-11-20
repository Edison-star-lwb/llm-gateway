import threading

_lock = threading.Lock()
_counters = {
    "requests_total": 0,
    "status_2xx": 0,
    "status_4xx": 0,
    "status_5xx": 0,
    "in_flight": 0,
}
_by_caller: dict[str, int] = {}


def inc_request():
    with _lock:
        _counters["requests_total"] += 1
        _counters["in_flight"] += 1


def dec_request(status_code: int, caller: str = "unknown"):
    with _lock:
        _counters["in_flight"] -= 1
        if 200 <= status_code < 300:
            _counters["status_2xx"] += 1
        elif 400 <= status_code < 500:
            _counters["status_4xx"] += 1
        else:
            _counters["status_5xx"] += 1
        _by_caller[caller] = _by_caller.get(caller, 0) + 1


def snapshot() -> dict:
    with _lock:
        return {
            **_counters,
            "by_caller": dict(_by_caller),
        }
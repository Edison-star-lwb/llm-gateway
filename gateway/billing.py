import json
from datetime import datetime, timezone
from pathlib import Path

_ENC = None
_ENC_FAILED = False

def _encoding():
    global _ENC, _ENC_FAILED
    if _ENC is None and not _ENC_FAILED:
        import tiktoken
        _ENC = tiktoken.get_encoding("cl100k_base")
    return _ENC

def estimate_tokens(text: str) -> tuple[int, str]:
    global _ENC_FAILED
    try:
        enc = _encoding()
        if enc is None:
            raise RuntimeError("no encoding")
        return len(enc.encode(text)), "estimated"
    except Exception:
        _ENC_FAILED = True
        return max(1, int(len(text) * 1.3)), "fallback"

LEDGER_PATH = "data/ledger.jsonl"

def append_ledger(row: dict, path: str = LEDGER_PATH) -> None:
    """追加一行账。目录不存在就建，ts 没有就补。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    row.setdefault("ts", datetime.now(timezone.utc).isoformat())
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
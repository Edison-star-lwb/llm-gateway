"""Async load test tool: measures RPS, p50/p95 latency against gateway."""
import argparse
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

import httpx


async def send_request(
    client: httpx.AsyncClient,
    base_url: str,
    key: str,
    model: str,
    stream: bool,
    semaphore: asyncio.Semaphore,
) -> dict:
    """发一个请求，返回 {status, latency_ms, first_token_ms, error}"""
    async with semaphore:
        start = time.perf_counter()
        first_token_ms = None
        try:
            if stream:
                async with client.stream(
                    "POST",
                    f"{base_url}/chat/stream",
                    headers={"X-API-Key": key},
                    json={"model": model, "message": "hi"},
                    timeout=60,
                ) as resp:
                    status = resp.status_code
                    async for chunk in resp.aiter_lines():
                        if first_token_ms is None and chunk:
                            first_token_ms = (time.perf_counter() - start) * 1000
                        if chunk == "data: [DONE]":
                            break
            else:
                resp = await client.post(
                    f"{base_url}/v1/chat/completions",
                    headers={"X-API-Key": key},
                    json={"model": model, "messages": [{"role": "user", "content": "hi"}]},
                    timeout=60,
                )
                status = resp.status_code
                await resp.aread()

            latency_ms = (time.perf_counter() - start) * 1000
            return {
                "status": status,
                "latency_ms": latency_ms,
                "first_token_ms": first_token_ms,
                "error": None,
            }
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return {
                "status": 0,
                "latency_ms": latency_ms,
                "first_token_ms": None,
                "error": str(e),
            }


async def run_bench(
    base_url: str,
    key: str,
    concurrency: int,
    total: int,
    model: str,
    stream: bool,
) -> list[dict]:
    semaphore = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient() as client:
        tasks = [
            send_request(client, base_url, key, model, stream, semaphore)
            for _ in range(total)
        ]
        return await asyncio.gather(*tasks)


def compute_metrics(results: list[dict]) -> dict:
    total = len(results)
    success = sum(1 for r in results if r["status"] == 200)
    errors_by_status = {}
    for r in results:
        if r["status"] != 200:
            errors_by_status[r["status"]] = errors_by_status.get(r["status"], 0) + 1

    latencies = sorted(r["latency_ms"] for r in results if r["status"] == 200)
    
    if not latencies:
        return {
            "total": total,
            "success": 0,
            "errors": errors_by_status,
            "rps": 0,
            "p50_ms": None,
            "p95_ms": None,
            "max_ms": None,
            "first_token_p50_ms": None,
            "first_token_p95_ms": None,
        }

    p50 = latencies[len(latencies) * 50 // 100]
    p95 = latencies[len(latencies) * 95 // 100]
    max_lat = latencies[-1]

    first_tokens = sorted(
        r["first_token_ms"] for r in results if r["first_token_ms"] is not None
    )
    ft_p50 = first_tokens[len(first_tokens) * 50 // 100] if first_tokens else None
    ft_p95 = first_tokens[len(first_tokens) * 95 // 100] if first_tokens else None

    total_time = max(r["latency_ms"] for r in results) / 1000
    rps = success / total_time if total_time > 0 else 0

    return {
        "total": total,
        "success": success,
        "errors": errors_by_status,
        "rps": round(rps, 2),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "max_ms": round(max_lat, 2),
        "first_token_p50_ms": round(ft_p50, 2) if ft_p50 else None,
        "first_token_p95_ms": round(ft_p95, 2) if ft_p95 else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--concurrency", type=int, required=True)
    parser.add_argument("--total", type=int, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--stream", action="store_true")
    args = parser.parse_args()

    results = asyncio.run(
        run_bench(args.base_url, args.key, args.concurrency, args.total, args.model, args.stream)
    )
    metrics = compute_metrics(results)

    print("\n=== Bench Summary ===")
    print(f"Total:      {metrics['total']}")
    print(f"Success:    {metrics['success']}")
    print(f"Errors:     {metrics['errors']}")
    print(f"RPS:        {metrics['rps']}")
    print(f"p50:        {metrics['p50_ms']} ms")
    print(f"p95:        {metrics['p95_ms']} ms")
    print(f"Max:        {metrics['max_ms']} ms")
    if metrics.get("first_token_p50_ms"):
        print(f"FT p50:     {metrics['first_token_p50_ms']} ms")
        print(f"FT p95:     {metrics['first_token_p95_ms']} ms")

    out = Path("bench_result.json")
    out.write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
    print(f"\nJSON saved to {out}")


if __name__ == "__main__":
    main()
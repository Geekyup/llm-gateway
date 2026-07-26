#!/usr/bin/env python3
"""Нагрузочный скрипт для keypool gateway — проверка балансировки/failover.

Шлёт N запросов на /v1/chat/completions параллельно (с ограничением
одновременных соединений), считает статистику по статус-кодам и
задержкам. Какой конкретно API-ключ из пула отработал каждый запрос —
не видно в HTTP-ответе (это внутренняя деталь gateway), поэтому смотри
на это в реальном времени в Live Monitor на дашборде, пока скрипт
работает — там как раз показывается key_label по каждому запросу.

Использование:
    python3 hammer.py --requests 100
    python3 hammer.py --requests 30 --concurrency 3 --delay 1.0
    python3 hammer.py --requests 50 --model gemini-3.6-flash

По умолчанию скрипт бьёт мягко (concurrency=5, delay=0.5s между запросами
внутри слота), чтобы не выбить rate limit у всех ключей пула сразу — на
free tier Gemini лимит часто около 5-15 req/min НА КЛЮЧ, и параллельный
залп быстро загоняет весь пул в COOLDOWN на час разом (тогда сервер
начинает отвечать 503 — "нет доступных ключей").

Требует: pip install httpx --break-system-packages
"""

import argparse
import asyncio
import time
from collections import Counter

import httpx

BASE_URL = "https://llm-gateway-production-c681.up.railway.app"
GATEWAY_TOKEN = "gwk_1GJsTmOdOlaSLkPP42spij1FED1u2-sxtYD85YoNJ4M"


async def send_one(client: httpx.AsyncClient, sem: asyncio.Semaphore, idx: int, model: str, delay: float) -> dict:
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": f"Reply with just the number {idx}."}
        ],
        "max_tokens": 16,
    }
    started = time.monotonic()
    async with sem:
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            resp = await client.post("/v1/chat/completions", json=payload)
            elapsed = time.monotonic() - started
            body_snippet = None
            if resp.status_code >= 400:
                try:
                    body_snippet = resp.json()
                except Exception:  # noqa: BLE001 - not JSON, fall back to raw text
                    body_snippet = resp.text[:300]
            return {"idx": idx, "status": resp.status_code, "elapsed": elapsed, "error": None, "body": body_snippet}
        except Exception as exc:  # noqa: BLE001 - report and keep going
            elapsed = time.monotonic() - started
            return {"idx": idx, "status": None, "elapsed": elapsed, "error": str(exc), "body": None}


async def run(total: int, concurrency: int, model: str, delay: float) -> None:
    sem = asyncio.Semaphore(concurrency)
    headers = {
        "Authorization": f"Bearer {GATEWAY_TOKEN}",
        "Content-Type": "application/json",
    }

    print(f"→ {total} запросов, до {concurrency} одновременно, задержка {delay}s перед каждым, модель={model}")
    print(f"→ {BASE_URL}/v1/chat/completions\n")

    started = time.monotonic()
    done = 0
    results: list[dict] = []

    async with httpx.AsyncClient(base_url=BASE_URL, headers=headers, timeout=60.0) as client:
        tasks = [asyncio.create_task(send_one(client, sem, i, model, delay)) for i in range(total)]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            done += 1
            status = result["status"] or "ERR"
            print(f"[{done}/{total}] #{result['idx']:04d}  status={status}  {result['elapsed']*1000:.0f}ms", flush=True)
            if result.get("body"):
                print(f"           ↳ {result['body']}", flush=True)
            if result.get("error"):
                print(f"           ↳ {result['error']}", flush=True)

    total_elapsed = time.monotonic() - started

    status_counts = Counter(r["status"] if r["status"] else "error" for r in results)
    latencies = sorted(r["elapsed"] for r in results if r["status"])
    errors = [r for r in results if r["error"]]

    print("\n" + "=" * 50)
    print("ИТОГО")
    print("=" * 50)
    print(f"Всего запросов:   {total}")
    print(f"Время выполнения: {total_elapsed:.1f}s ({total/total_elapsed:.1f} req/s)")
    print("\nПо статус-кодам:")
    for status, count in sorted(status_counts.items(), key=lambda x: str(x[0])):
        print(f"  {status}: {count}")

    if latencies:
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        print(f"\nЗадержка: min={latencies[0]*1000:.0f}ms  p50={p50*1000:.0f}ms  "
              f"p95={p95*1000:.0f}ms  max={latencies[-1]*1000:.0f}ms")

    if errors:
        print(f"\n{len(errors)} запросов упали с сетевой ошибкой (первые 5):")
        for e in errors[:5]:
            print(f"  #{e['idx']}: {e['error']}")

    if status_counts.get(429):
        print("\n⚠ Есть 429 — ключи упираются в rate limit самого Gemini "
              "(не гейтвея). Каждый такой 429 переводит ключ в COOLDOWN на 1 час.")
    if status_counts.get(503):
        print("\n⚠ Есть 503 — это значит, что ВСЕ ключи пула одновременно ушли "
              "в cooldown/exhausted, и обслуживать запросы стало нечем "
              "(NoAvailableKeysError / UpstreamExhaustedError). Если так, весь "
              "пул завис в cooldown ещё на час — либо жди, либо сбрасывай "
              "cooldown вручную на дашборде (кнопка Reset Cooldown на ключе).")
    if status_counts.get(200, 0) == total:
        print("\n✓ Все запросы успешны — пул продержался под нагрузкой.")

    print("\nПроверь Live Monitor на дашборде — там видно, какие именно ключи "
          "отрабатывали каждый запрос (key_label) и была ли ротация между ними.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load test for keypool gateway")
    parser.add_argument("--requests", "-n", type=int, required=True, help="Сколько запросов сделать")
    parser.add_argument("--concurrency", "-c", type=int, default=5, help="Сколько запросов одновременно (по умолчанию 5 — мягко, чтобы не выбить лимиты сразу)")
    parser.add_argument("--model", "-m", type=str, default="gemini-3.6-flash", help="Имя модели (по умолчанию gemini-3.6-flash)")
    parser.add_argument("--delay", "-d", type=float, default=0.5, help="Задержка в секундах перед каждым запросом (по умолчанию 0.5s)")
    args = parser.parse_args()

    if args.requests <= 0:
        parser.error("--requests должно быть больше 0")
    if args.concurrency <= 0:
        parser.error("--concurrency должно быть больше 0")
    if args.delay < 0:
        parser.error("--delay не может быть отрицательным")

    asyncio.run(run(args.requests, args.concurrency, args.model, args.delay))


if __name__ == "__main__":
    main()
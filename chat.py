"""
Простой терминальный чат-клиент для llm-gateway (OpenAI-совместимый эндпоинт).

Использование:
    export GATEWAY_TOKEN="gwk_..."
    export GATEWAY_URL="http://localhost:8000"   # адрес твоего backend
    python3 chat.py

Если переменные не заданы — скрипт спросит их интерактивно (токен не будет
отображаться в истории терминала, если запускать через export).
"""

import os
import sys
import json
import urllib.request
import urllib.error

# Модель Gemini, которую поддерживает твой gateway (можно поменять)
MODEL = "gemini-3.6-flash"

# Адрес твоего backend на Railway (используется, если GATEWAY_URL не задан)
DEFAULT_GATEWAY_URL = "https://llm-gateway-production-c681.up.railway.app"


def get_config():
    url = os.environ.get("GATEWAY_URL", "").rstrip("/") or DEFAULT_GATEWAY_URL
    token = os.environ.get("GATEWAY_TOKEN", "")

    if not token:
        token = input("Gateway token (gwk_...): ").strip()

    return url, token


def send_message(url: str, token: str, messages: list[dict]) -> str:
    endpoint = f"{url}/v1/chat/completions"

    body = {
        "model": MODEL,
        "messages": messages,
    }

    data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        print(f"\n[Ошибка HTTP {e.code}]: {raw}\n")
        return None
    except urllib.error.URLError as e:
        print(f"\n[Не удалось подключиться к gateway]: {e}\n")
        return None

    parsed = json.loads(raw)

    try:
        return parsed["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        print(f"\n[Неожиданный формат ответа]: {parsed}\n")
        return None


def main():
    # Заставляем stdout/stdin работать в UTF-8, чтобы кириллица не ломалась
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")

    url, token = get_config()

    if not url or not token:
        print("Нужны URL и токен. Выход.")
        return

    print(f"\nПодключение к {url} (модель: {MODEL})")
    print("Пиши сообщение и жми Enter. Для выхода — /exit или Ctrl+C.\n")

    history: list[dict] = []

    while True:
        try:
            user_input = input("Вы: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nПока!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("/exit", "/quit"):
            print("Пока!")
            break

        history.append({"role": "user", "content": user_input})

        answer = send_message(url, token, history)

        if answer is None:
            # Не добавляем неудачный запрос в историю, чтобы не путать контекст
            history.pop()
            continue

        print(f"Бот: {answer}\n")
        history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
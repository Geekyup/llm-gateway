"""
Простой терминальный чат-клиент для llm-gateway (OpenAI-совместимый эндпоинт).

Использование:
    export GATEWAY_TOKEN="gwk_..."
    export GATEWAY_URL="http://localhost:8000"   # адрес твоего backend
    python3 chat.py

Если переменные не заданы — скрипт спросит их интерактивно (токен не будет
отображаться в истории терминала, если запускать через export).

При старте нужно выбрать провайдера (Gemini / OpenRouter) и ввести имя
модели вручную — сам чат работает через gateway-токен, а не сырой ключ
провайдера, поэтому живой список моделей (как на сайте, через
/me/keys/list-models) тут недоступен: тот эндпоинт требует именно сырой
ключ провайдера. Модель нужно знать заранее (например из документации
провайдера или из панели ключа на сайте).

Требует: pip install httpx
"""

import asyncio
import os
import sys

import httpx

# Адрес твоего backend на Railway (используется, если GATEWAY_URL не задан)
DEFAULT_GATEWAY_URL = "https://llm-gateway-production-c681.up.railway.app"

# Провайдеры, поддерживаемые гейтвеем, и пример модели для каждого —
# только подсказка в приглашении ввода, не единственный вариант.
PROVIDERS = {
    "1": ("gemini", "gemini-3.6-flash"),
    "2": ("openrouter", "openai/gpt-4o-mini"),
}


def get_config() -> tuple[str, str]:
    url = os.environ.get("GATEWAY_URL", "").rstrip("/") or DEFAULT_GATEWAY_URL
    token = os.environ.get("GATEWAY_TOKEN", "")

    if not token:
        token = input("Gateway token (gwk_...): ").strip()

    return url, token


def choose_provider_and_model() -> tuple[str, str]:
    print("Какой провайдер использовать?")
    for key, (name, _) in PROVIDERS.items():
        print(f"  {key}) {name}")

    choice = ""
    while choice not in PROVIDERS:
        choice = input("Выбор [1/2]: ").strip()
        if choice not in PROVIDERS:
            print("Не понял, введи 1 или 2.")

    provider, example_model = PROVIDERS[choice]

    model = input(f"Модель для {provider} (например {example_model}): ").strip()
    while not model:
        model = input("Модель не может быть пустой, введи ещё раз: ").strip()

    return provider, model


async def send_message(
    client: httpx.AsyncClient, token: str, provider: str, model: str, messages: list[dict]
) -> str | None:
    body = {
        "model": model,
        "provider": provider,
        "messages": messages,
    }

    try:
        resp = await client.post(
            "/v1/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
    except httpx.HTTPError as e:
        print(f"\n[Не удалось подключиться к gateway]: {e}\n")
        return None

    if resp.status_code >= 400:
        print(f"\n[Ошибка HTTP {resp.status_code}]: {resp.text}\n")
        return None

    parsed = resp.json()
    try:
        return parsed["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        print(f"\n[Неожиданный формат ответа]: {parsed}\n")
        return None


async def main() -> None:
    # Заставляем stdout/stdin работать в UTF-8, чтобы кириллица не ломалась
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")

    url, token = get_config()

    if not url or not token:
        print("Нужны URL и токен. Выход.")
        return

    provider, model = choose_provider_and_model()

    print(f"\nПодключение к {url} (провайдер: {provider}, модель: {model})")
    print("Пиши сообщение и жми Enter. Для выхода — /exit или Ctrl+C.\n")

    history: list[dict] = []

    async with httpx.AsyncClient(base_url=url) as client:
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

            answer = await send_message(client, token, provider, model, history)

            if answer is None:
                # Не добавляем неудачный запрос в историю, чтобы не путать контекст
                history.pop()
                continue

            print(f"Бот: {answer}\n")
            history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    asyncio.run(main())
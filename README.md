# llm-gateway

OpenAI-совместимый шлюз перед Gemini, Groq и OpenRouter. Кидаешь ему пачку
своих ключей — он сам их ротирует, ловит `429`, ставит проблемный ключ на
cooldown и переключается на следующий. Один эндпоинт
`/v1/chat/completions`, дальше не важно, кто там реально отвечает.

Плюс дашборд, где видно живьём, что происходит с ключами и куда уходит квота.

## Зачем

Бесплатные/личные ключи Gemini, Groq и OpenRouter быстро упираются в лимиты.
Обычно это решают либо руками (переключать ключ при ошибке), либо
самописным failover-кодом под каждого провайдера. Здесь это сделано один раз
и спрятано за стандартным OpenAI SDK.

## Что внутри

- Ротация ключей и авто-failover при `429` / исчерпании квоты
- OpenAI-совместимый `/v1/chat/completions` (+ стриминг) для Gemini, Groq, OpenRouter
- Дашборд: живой монитор запросов (SSE), графики usage/токенов по ключам, health-check в один клик
- Вход через Google OAuth, отдельные отзываемые gateway-токены для самого API
- Фоновый воркер снимает cooldown'ы и сбрасывает дневные лимиты сам
- 
## Стек

**Backend**

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0_async-D71F00?logo=sqlalchemy&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)
![ARQ](https://img.shields.io/badge/ARQ-background_jobs-black)
![Alembic](https://img.shields.io/badge/Alembic-migrations-blue)

**Frontend**

![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-6-646CFF?logo=vite&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind-v4-06B6D4?logo=tailwindcss&logoColor=white)
![Recharts](https://img.shields.io/badge/Recharts-charts-8884d8)

## Быстрый старт

```bash
git clone https://github.com/Geekyup/llm-gateway.git
cd llm-gateway
cp .env.example .env
```

Сгенерируй ключ шифрования и вставь в `.env` (`ENCRYPTION_KEY`):

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`JWT_SECRET_KEY`, `SESSION_SECRET_KEY`, `ADMIN_API_KEY` — любые длинные
случайные строки.

```bash
docker compose up --build
```

Готово: API на `localhost:8000` (Swagger — `/docs`), дашборд — на
`localhost:5173`.

<details>
<summary>Запуск без Docker</summary>

```bash
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload

# в отдельном терминале — воркер
arq app.housekeeping.arq_worker.WorkerSettings
```

Фронтенд отдельно:

```bash
cd frontend && npm install && npm run dev
```

</details>

## Использование

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="<gateway-access-token>",  # создаётся в дашборде
)

response = client.chat.completions.create(
    model="gemini-2.0-flash",
    messages=[{"role": "user", "content": "Привет!"}],
)
```

Провайдер можно задать явно полем `provider` (`gemini` / `groq` /
`openrouter`), иначе шлюз выбирает сам — по модели и живым ключам.

## Как это устроено

```
Клиент ──► /v1/chat/completions ──► выбор здорового ключа ──► провайдер
                                            │
                              429/exhausted → cooldown, retry на следующем
                                            │
                              200 → событие в Redis (live-монитор)
                                       + в Postgres (графики usage)
```

Роуты тонкие, вся логика ротации/cooldown — в сервисном слое, доступ к БД —
через репозитории. Адаптеры провайдеров (`app/providers/`) прячут разницу
форматов Gemini/Groq/OpenRouter за одним интерфейсом. ARQ гоняет
housekeeping-задачи по расписанию вместо cron-скриптов.

## Тесты

```bash
python -m pytest -v
python -m ruff check app
```
# llm-gateway

OpenAI-совместимый API-шлюз перед Gemini и OpenRouter, который ротирует пул
собственных API-ключей, чтобы клиентской интеграции никогда не приходилось
думать про рейт-лимиты, исчерпанные квоты или то, какой провайдер стоит за
конкретной моделью.

**Для кого:** для тех, кто упирается в лимиты бесплатных/общих API-ключей —
пет-проекты, небольшие команды или личные инструменты — и хочет один
стабильный OpenAI-совместимый эндпоинт вместо ручного написания
retry/failover-логики под каждого провайдера, плюс дашборд, чтобы реально
видеть в реальном времени, что происходит с этими ключами.

**Какую проблему решает:** один Gemini- или OpenRouter-ключ ловит 429 —
и приложение просто ломается. Жонглировать несколькими ключами вручную
в команде или писать failover-логику под каждого провайдера — не
масштабируется. Этот шлюз берёт ротацию на себя один раз, за единым
эндпоинтом `/v1/chat/completions`, и даёт админку, чтобы добавлять ключи,
следить за квотами и видеть запросы по мере их поступления.

---

## Стек технологий

**Backend**

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0_async-D71F00?logo=sqlalchemy&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)
![ARQ](https://img.shields.io/badge/ARQ-background_jobs-black)
![Alembic](https://img.shields.io/badge/Alembic-migrations-blue)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?logo=pydantic&logoColor=white)

**Frontend**

![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-6-646CFF?logo=vite&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/Tailwind-v4-06B6D4?logo=tailwindcss&logoColor=white)
![Recharts](https://img.shields.io/badge/Recharts-charts-8884d8)

**Инфраструктура и тулинг**

![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Railway](https://img.shields.io/badge/Railway-deploy-0B0D0E?logo=railway&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/CI-GitHub_Actions-2088FF?logo=githubactions&logoColor=white)
![Ruff](https://img.shields.io/badge/Lint-Ruff-D7FF64)
![Pytest](https://img.shields.io/badge/Tests-Pytest-0A9EDC?logo=pytest&logoColor=white)

---

## Функциональность

- **OpenAI-совместимый эндпоинт** — направь любой OpenAI SDK/клиент на
  `/v1/chat/completions`, и всё просто работает, независимо от того,
  реально запрос уходит в Gemini или в OpenRouter за кулисами.
- **Автоматическая ротация ключей и failover** — при `429` шлюз ставит
  этот ключ на cooldown-таймер и повторяет запрос на следующем здоровом
  ключе из пула, прозрачно для вызывающей стороны.
- **Учёт квот по каждому ключу** — дневные лимиты запросов на ключ, ключи
  автоматически переходят в `COOLDOWN` (временно) или `EXHAUSTED` (нужен
  человек) в зависимости от того, как ответил провайдер.
- **Вход через Google OAuth** — админ-дашборд и управление ключами
  привязаны к конкретному авторизованному пользователю, а не к единому
  общему админ-паролю.
- **Gateway access tokens** — отдельные, отзываемые токены для самого
  прокси-эндпоинта, независимые от сессии логина в дашборде.
- **Живой монитор запросов** — поток Server-Sent Events показывает
  запросы к шлюзу в реальном времени, без поллинга.
- **Дашборды использования** — почасовые графики запросов и токенов
  (prompt / completion / total) по каждому ключу, чтобы точно видеть,
  куда уходит квота.
- **Health-check в один клик** — проверка, что ключ ещё работает у
  провайдера, без расхода квоты на генерацию.
- **Фоновая housekeeping-логика** — запланированный воркер снимает
  истёкшие cooldown'ы, сбрасывает дневные лимиты и повторно проверяет
  исчерпанные ключи на случай, если они восстановились у провайдера.

---

## Инструкция по запуску

### Требования

- Docker и Docker Compose
- Gemini API-ключ ([Google AI Studio](https://aistudio.google.com/apikey))
  и/или [OpenRouter](https://openrouter.ai) API-ключ
- Google OAuth client ID/secret (для входа в дашборд) — опционально, если
  нужен только прокси, обязательно для админ-панели

### Настройка

```bash
git clone https://github.com/Geekyup/llm-gateway.git
cd llm-gateway
cp .env.example .env
```

Открой `.env` и заполни необходимые переменные:

```bash
# Сгенерировать Fernet-ключ для шифрования хранимых ключей провайдеров:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Вставь результат в `ENCRYPTION_KEY`, а `JWT_SECRET_KEY` / `SESSION_SECRET_KEY`
/ `ADMIN_API_KEY` заполни любыми длинными случайными строками.

### Запуск всего стека

```bash
docker compose up --build
```

Поднимет Postgres, Redis, прогонит миграции Alembic, затем запустит API
(`:8000`), фоновый воркер и фронтенд (`:5173`).

### Запуск бэкенда отдельно (без Docker)

```bash
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

### Тесты

```bash
pytest -v
ruff check app tests
```

### Только фронтенд

```bash
cd frontend
npm install
npm run dev
```


## Архитектура

```
Клиент (OpenAI SDK)
        │
        ▼
 /v1/chat/completions  ──────────────►  Селектор ключей (Postgres)
        │                                      │
        │                       выбор здорового ключа для провайдера
        ▼                                      ▼
  Адаптер провайдера (Gemini / OpenRouter) ◄────┘
        │
        ├─ 200 → фиксируем успех, извлекаем usage, публикуем событие
        ├─ 429 → ключ → COOLDOWN, retry на следующем ключе
        └─ исчерпан (403/402) → ключ → EXHAUSTED, retry на следующем ключе
        │
        ├──────────────┬───────────────────────────┐
        ▼               ▼                            ▼
   Redis pub/sub   Redis ограниченный          Postgres request_events
    (fan-out)      список на юзера            (персистентный лог)
        │                │                            │
        ▼                ▼                            ▼
  Живой монитор    /me/monitor/recent          Почасовые графики
     (SSE)         (последние N событий)        usage / токенов
```

- **Слои router → service → repository** по всему проекту — роуты тонкие,
  бизнес-правила (ротация, cooldown, сброс квот) живут в сервисах, а
  доступ к Postgres изолирован за репозиториями.
- **Адаптеры провайдеров** ([`app/providers/`](app/providers/)) реализуют один небольшой
  интерфейс (`forward`, `is_rate_limited`, `is_key_exhausted`,
  `health_check`, `list_models`) на каждого апстрима. Gemini и OpenRouter
  говорят на разных форматах — Gemini требует трансляции запроса/ответа
  для OpenAI-совместимого эндпоинта, OpenRouter уже в OpenAI-формате — но
  логике retry/ротации в шлюзе не нужно знать об этой разнице.
- **ARQ** гоняет запланированные housekeeping-задачи (снятие истёкших
  cooldown'ов, сброс дневных лимитов, повторная проверка исчерпанных
  ключей, ежедневная очистка старых `request_events`) вместо самопального
  cron+скрипта — так retry/расписание обрабатываются полноценной очередью
  задач, уже подключённой к тому же Redis.
- **Мониторинг — двойная запись, разделённая по назначению.** Каждое
  событие запроса публикуется в Redis pub/sub (живой SSE-поток на все
  подключённые дашборды) и одновременно, best-effort, пишется в таблицу
  `request_events` в Postgres. Redis отвечает только за то, что происходит
  прямо сейчас — короткий буфер на пользователя, чтобы дашборд, открытый
  после того, как прошёл трафик, не смотрел на пустой экран. Postgres —
  единственный источник для почасовых графиков usage/токенов и любой
  будущей аналитики; сбой записи в него никогда не блокирует сам ответ
  прокси или живой поток.


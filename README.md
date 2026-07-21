# LLM Gateway

Gateway API с пулом Gemini API ключей, ротацией (round-robin) и прозрачным
failover при 429. Клиент бьёт в один эндпоинт, не зная, сколько ключей за
ним стоит и что произошло переключение.

## Быстрый старт

```bash
cp .env.example .env
# сгенерировать ENCRYPTION_KEY:
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# вписать его и любой длинный рандомный ADMIN_API_KEY в .env

docker compose up --build
```

Поднимутся: `api` (FastAPI, :8000), `worker` (ARQ housekeeping), `postgres`,
`redis`, `frontend` (админ-панель, :5173), плюс одноразовый `migrate`
(применяет Alembic-миграции перед стартом api/worker).

Проверка:
```bash
curl http://localhost:8000/health
# {"status": "ok"}
```
Панель управления — http://localhost:5173 (подробности в разделе
[Frontend](#frontend-админ-панель) ниже).

## Добавить ключ в пул

```bash
curl -X POST http://localhost:8000/admin/keys \
  -H "Authorization: Bearer $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "gemini-account-1",
    "provider": "gemini",
    "raw_key": "AIza...",
    "daily_limit": 1500
  }'
```

Список ключей (без расшифрованных секретов — только метаданные):
```bash
curl http://localhost:8000/admin/keys -H "Authorization: Bearer $ADMIN_API_KEY"
```

## Gateway Access Tokens (единый ключ для твоего приложения)

`ADMIN_API_KEY` даёт полный доступ к управлению пулом (`/admin/*`) — им
не стоит светить в клиентских приложениях. Для них есть отдельная сущность:
**Gateway Token** — один короткий токен, который объединяет доступ ко
**всем** ключам в пуле разом. Приложение бьёт в `/v1/...` с этим токеном,
не зная (и не должно знать), какой именно ключ Gemini использовался —
ротацию и failover gateway делает сам, прозрачно.

Создать токен (обычно через дашборд, вкладка **Gateway Access**, но можно
и через API):
```bash
curl -X POST http://localhost:8000/admin/gateway-tokens \
  -H "Authorization: Bearer $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"label": "kitroom-backend"}'
# {"token": {...}, "plaintext": "gwk_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"}
```
`plaintext` показывается **один раз**, в момент создания — сохрани его сразу.
В базе хранится только его sha256-хэш, восстановить исходное значение потом
нельзя, только сгенерировать новый токен.

Отозвать/снова активировать/удалить:
```bash
curl -X POST http://localhost:8000/admin/gateway-tokens/1/revoke  -H "Authorization: Bearer $ADMIN_API_KEY"
curl -X POST http://localhost:8000/admin/gateway-tokens/1/activate -H "Authorization: Bearer $ADMIN_API_KEY"
curl -X DELETE http://localhost:8000/admin/gateway-tokens/1        -H "Authorization: Bearer $ADMIN_API_KEY"
```

## Проксирование запроса к Gemini

```bash
curl -X POST http://localhost:8000/v1/gemini/v1beta/models/gemini-1.5-flash:generateContent \
  -H "Authorization: Bearer $GATEWAY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"contents":[{"parts":[{"text":"Привет!"}]}]}'
```

`$GATEWAY_TOKEN` — тот самый `plaintext` из шага выше (это НЕ `ADMIN_API_KEY`).
Без валидного gateway-токена `/v1/*` отвечает `401 Invalid or revoked gateway token`.

Gateway сам выберет активный ключ (round-robin), при 429 от Gemini —
пометит ключ в cooldown и прозрачно повторит запрос со следующим ключом
(до `GATEWAY_MAX_RETRY_ATTEMPTS` попыток). Если все ключи исчерпаны —
вернёт `503` с телом вида `{"error": "upstream_exhausted", ...}`.

## Живой мониторинг запросов

Каждый хоп проксирования (выбор ключа → вызов апстрима → success/429/403)
публикуется как событие в Redis Pub/Sub и дублируется в короткую историю
(последние 200 событий), не блокируя основной поток — сбой публикации
никогда не роняет сам запрос.

Снимок последних событий (для первичной отрисовки дашборда):
```bash
curl http://localhost:8000/admin/monitor/recent?limit=50 \
  -H "Authorization: Bearer $ADMIN_API_KEY"
```

Живой поток через Server-Sent Events:
```bash
curl -N http://localhost:8000/admin/monitor/stream \
  -H "Authorization: Bearer $ADMIN_API_KEY"
```

Каждое событие (`RequestEvent`) содержит: `request_id` (общий для всех
попыток одного клиентского запроса — так фронтенд может собрать цепочку
retry в одну карточку), `attempt`, `provider`, `key_id`/`key_label`,
`upstream_status`, `outcome` (`success` / `rate_limited` / `exhausted` /
`no_keys` / `upstream_exhausted`), `latency_ms`, `is_retry`.

Пример цепочки failover для одного клиентского запроса — два события с
одним `request_id`: `attempt=1 outcome=rate_limited` (ключ A получил 429),
`attempt=2 outcome=success` (ключ B ответил 200).

## Frontend (админ-панель)

В `frontend/` лежит React + Vite панель управления пулом ключей: таблица
ключей с статусами/квотами, добавление/редактирование/удаление, ручной
сброс cooldown, вкладка Live Monitor с потоком событий из `/admin/monitor/stream`,
и вкладка **Gateway Access** — генерация/отзыв клиентских токенов (см. раздел
[Gateway Access Tokens](#gateway-access-tokens-единый-ключ-для-твоего-приложения) выше).

### Запуск через Docker Compose

Важно: `frontend`-образ **не собирает** фронтенд внутри Docker (на
некоторых Windows/WSL2 машинах Docker не может достучаться до npm-реестра,
даже если сам хост — может, и `npm install` внутри контейнера зависает
намертво). Вместо этого фронтенд собирается один раз на хосте, а Docker
просто раздаёт готовые файлы через nginx.

**Шаг 1 — собери фронтенд на хосте** (нужен Node.js 18+, ставится с
[nodejs.org](https://nodejs.org)):
```bash
cd frontend
cp .env.example .env       # VITE_API_URL=http://localhost:8000 по умолчанию
npm install
npm run build               # создаст frontend/dist/
cd ..
```

**Шаг 2 — подними всё через Docker Compose:**
```bash
docker compose up --build
# фронтенд:  http://localhost:5173
# API:       http://localhost:8000
```

При первом входе панель попросит `ADMIN_API_KEY` — тот же токен, что в
`.env` бэкенда. Он сохраняется только в localStorage браузера.

Если поменял `VITE_API_URL` в `frontend/.env` — пересобери:
```bash
cd frontend && npm run build && cd ..
docker compose build frontend && docker compose up -d frontend
```

**Если у тебя Docker нормально резолвит npm-реестр** (проверить: `docker
run --rm node:20-slim npm ping` не виснет) — можно вместо ручной сборки
собрать фронтенд полностью внутри Docker:
```bash
docker build -f frontend/Dockerfile.docker-build -t llm-gateway-frontend ./frontend
docker run -p 5173:80 llm-gateway-frontend
```

### Локальная разработка фронтенда (с hot-reload, без Docker)
```bash
cd frontend
cp .env.example .env       # VITE_API_URL=http://localhost:8000 по умолчанию
npm install
npm run dev                # http://localhost:5173
```
Бэкенд при этом должен быть поднят отдельно (`docker compose up -d postgres redis migrate api`
или `uvicorn llm_gateway.main:app --reload`), и в `.env` бэкенда должен быть
указан адрес фронтенда в `CORS_ORIGINS` (по умолчанию уже включает
`http://localhost:5173`).

**Сборка статики без Docker:**
```bash
cd frontend
npm run build      # результат в frontend/dist/, раздавать любым статик-сервером
```

## Деплой на Railway

Проект — это 4 отдельных сервиса (`api`, `worker`, `frontend`, плюс managed
Postgres и Redis). Railway не читает `docker-compose.yml` напрямую — каждый
сервис создаётся отдельно и настраивается вручную один раз через дашборд.

### 1. Создай проект и managed-базы

В Railway: **New Project** → **Deploy from GitHub repo**, выбери этот
репозиторий. Затем в этом же проекте добавь:
- **New → Database → PostgreSQL**
- **New → Database → Redis**

Railway сам сгенерирует для них `DATABASE_URL`/`REDIS_URL` — их можно
подставить в переменные сервисов через referenced variables (`${{Postgres.DATABASE_URL}}`),
не копируя вручную.

⚠️ Обрати внимание: у Postgres Railway переменная называется `DATABASE_URL`
и обычно в формате `postgresql://...`, а этому проекту (SQLAlchemy async)
нужен префикс `postgresql+asyncpg://...` — либо переопредели переменную на
сервисе `api`/`worker` вручную, либо возьми хост/порт/базу из `PGHOST`,
`PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` (Railway их тоже даёт) и
собери строку самостоятельно:
```
postgresql+asyncpg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}
```

### 2. Сервис `api`

- **Root Directory**: `/` (корень репо — там уже лежит `Dockerfile` и `railway.json`)
- Railway подхватит `railway.json` автоматически: соберёт по `Dockerfile`,
  перед каждым деплоем выполнит `alembic upgrade head` (это заменяет
  отдельный сервис `migrate` из docker-compose — на Railway отдельный
  одноразовый контейнер не нужен).
- **Settings → Networking → Generate Domain** — получишь публичный URL вида
  `https://<name>.up.railway.app`. Это и есть адрес твоего API.
- Переменные окружения (Settings → Variables) — перенеси всё из `.env`:
  ```
  ADMIN_API_KEY=<длинная случайная строка>
  ENCRYPTION_KEY=<сгенерировать: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
  DATABASE_URL=postgresql+asyncpg://...  (см. пункт 1)
  REDIS_URL=${{Redis.REDIS_URL}}
  CORS_ORIGINS=https://<домен-фронтенда>.up.railway.app
  GEMINI_BASE_URL=https://generativelanguage.googleapis.com
  UPSTREAM_TIMEOUT_SECONDS=60
  GATEWAY_MAX_RETRY_ATTEMPTS=3
  DEFAULT_DAILY_LIMIT=1000
  KEY_STATUS_CACHE_TTL_SECONDS=30
  ```
  `CORS_ORIGINS` заполнишь после того, как узнаешь домен фронтенда (шаг 4) —
  можно оставить пустым/localhost и вернуться сюда позже.
- **Не указывай `PORT` вручную** — Railway передаёт его сам, Dockerfile уже
  читает `${PORT:-8000}`.

### 3. Сервис `worker`

- **New → Service → GitHub Repo**, тот же репозиторий ещё раз (Railway
  позволяет несколько сервисов из одного репо).
- **Root Directory**: `/` (тот же Dockerfile, что и у api — образ идентичный,
  меняется только команда запуска).
- **Settings → Deploy → Custom Start Command**:
  ```
  arq llm_gateway.housekeeping.arq_worker.WorkerSettings
  ```
  Это переопределяет `CMD` из Dockerfile для конкретно этого сервиса.
- Те же переменные окружения, что у `api` (`DATABASE_URL`, `REDIS_URL`,
  `ENCRYPTION_KEY` и т.д.) — worker обращается к тем же БД.
- Публичный домен воркеру не нужен (у него нет HTTP-сервера) — можно не
  генерировать Networking.

### 4. Сервис `frontend`

- **New → Service → GitHub Repo**, тот же репозиторий.
- **Root Directory**: `frontend`
- **Settings → Build → Dockerfile Path**: `Dockerfile.docker-build`
  (не основной `Dockerfile` — тот ждёт уже готовый `frontend/dist/` из
  локальной сборки, а `Dockerfile.docker-build` собирает всё внутри
  контейнера, что и нужно на Railway, где сеть при билде не ограничена).
- **Variables**:
  ```
  VITE_API_URL=https://<домен-api-из-шага-2>.up.railway.app
  ```
  Это build-time переменная (используется как `ARG` в Dockerfile) — Railway
  подставит её именно на этапе сборки образа.
- **Settings → Networking → Generate Domain** — получишь публичный адрес
  панели, например `https://kitroom-gateway.up.railway.app`.

### 5. Замкни CORS

Вернись на сервис `api` → Variables → пропиши реальный домен фронтенда в
`CORS_ORIGINS` (можно перечислить несколько через запятую). Передеплой
сервиса `api` подхватит новое значение.

### 6. Проверка

```bash
curl https://<домен-api>.up.railway.app/health
# {"status": "ok"}
```
Открой `https://<домен-frontend>.up.railway.app`, залогинься по
`ADMIN_API_KEY`, добавь ключ Gemini, сгенерируй Gateway Token — всё то же
самое, что локально, только уже с публичными адресами.

### Обновление после git push

Railway по умолчанию редеплоит сервис при пуше в отслеживаемую ветку — все
три сервиса (`api`, `worker`, `frontend`) передеплоятся независимо. Миграции
применяются автоматически перед стартом `api` (см. `railway.json`), вручную
ничего гонять не нужно.

## Локальная разработка без Docker

```bash
pip install -e ".[dev]"
pytest -q
```

Тесты используют in-memory SQLite и фейковый Redis — реальные Postgres/Redis
не нужны для юнит-тестов (`tests/keys/`, `tests/gateway/`).

Чтобы прогнать локально с реальным Postgres/Redis (например, если тесты
дополнят интеграционными):
```bash
docker compose up -d postgres redis
alembic upgrade head
uvicorn llm_gateway.main:app --reload
arq llm_gateway.housekeeping.arq_worker.WorkerSettings   # в отдельном терминале
```

## Архитектура

```
src/llm_gateway/
├── config.py            # Pydantic Settings (.env)
├── main.py               # FastAPI app factory
├── core/                 # exceptions, Fernet-шифрование, логирование
├── db/                    # async SQLAlchemy session, Redis pool
├── keys/                  # домен "пул ключей"
│   ├── models.py          # ORM APIKey
│   ├── repository.py      # persistence (CRUD, bulk-update для housekeeping)
│   ├── selector.py         # KeySelector strategy — RoundRobinSelector (курсор в Redis)
│   ├── cache.py            # KeyStatusCache — метаданные активных ключей в Redis
│   └── service.py          # KeyPoolService — оркестрирует repo+cache+selector
├── providers/              # адаптеры к внешним LLM API
│   ├── base.py             # Provider ABC (forward / is_rate_limited / is_key_exhausted)
│   ├── gemini.py            # GeminiProvider
│   └── registry.py          # provider_name -> Provider
├── gateway/                 # прокси-логика с failover
│   ├── proxy_service.py      # GatewayService: select -> forward -> retry on 429
│   └── router.py              # POST/GET /v1/{provider}/{path}
├── admin/                    # CRUD для ключей (Bearer-токен из ADMIN_API_KEY)
├── monitoring/                # живой мониторинг запросов
│   ├── schemas.py              # RequestEvent — одна попытка проксирования
│   ├── publisher.py             # Redis Pub/Sub + capped-list история, best-effort
│   └── router.py                 # GET /admin/monitor/recent, GET /admin/monitor/stream (SSE)
└── housekeeping/               # ARQ cron: сброс дневных лимитов, разморозка cooldown
```

**Поток запроса:**
`POST /v1/gemini/...` → `GatewayService.proxy_request` → `KeyPoolService.select_key`
(Redis-кэш метаданных → `RoundRobinSelector` → расшифровка ключа из БД
непосредственно перед вызовом) → `GeminiProvider.forward` → при 429:
`record_rate_limited` (cooldown в Postgres + инвалидация кэша) → retry с
другим ключом, максимум `GATEWAY_MAX_RETRY_ATTEMPTS` раз.

**Расширение на новых провайдеров:** реализовать `Provider` в
`providers/<name>.py`, зарегистрировать в `providers/registry.py`, добавить
значение в `keys/enums.py::ProviderType`. `GatewayService`, `KeyPoolService`,
`KeySelector` менять не нужно — они provider-agnostic.

**Что сознательно не реализовано в этом MVP** (см. `/areas/llm-gateway.md`
и исходный план в `LLM-Gateway-Project.md`):
- OpenAI-совместимый формат ответа (сейчас 1:1 проксирование тела Gemini)
- Weighted/least-used selector (интерфейс `KeySelector` уже это допускает)
- Telegram-бот для нотификаций
- GitHub Actions/Codespaces как второй тип ресурса в пуле

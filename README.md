# Developer Landing — Backend

Небольшой бэкенд-сервис для лендинга разработчика: контактная форма с валидацией,
rate limit, отправка писем на Яндекс.Почту, автоматический анализ обращения через LLM
(категория / тональность / черновик ответа) и метрики. Плюс минимальный статичный
лендинг с формой.

## Как запустить

### Локально

Нужен Python 3.12+ (проверял на 3.12 и 3.13). Версия для деплоя закреплена
в `runtime.txt` / `.python-version` = 3.12.7.

```bash
git clone <repo>
cd backendJun

python3 -m venv .venv
source .venv/bin/activate           # windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# заполнить переменные — минимум SMTP_* и OPENROUTER_API_KEY

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Откроется:

- лендинг с формой — http://localhost:8000
- Swagger UI — http://localhost:8000/docs
- ReDoc — http://localhost:8000/redoc

### Переменные окружения

Все настройки в `.env`. Пример — `.env.example`. Обязательные:

| Переменная | Что это |
|---|---|
| `OWNER_EMAIL` | Куда приходят уведомления о новых заявках |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | SMTP-креды (использую Яндекс, но подойдёт любой) |
| `SMTP_USE_TLS` | `true` для STARTTLS (587) или для implicit SSL (465) |
| `OPENROUTER_API_KEY` | Ключ OpenRouter. Если пустой — сервис работает через fallback без AI |
| `OPENROUTER_MODEL` | По умолчанию бесплатная `meta-llama/llama-3.1-8b-instruct:free` |
| `RATE_LIMIT_MAX`, `RATE_LIMIT_WINDOW_SECONDS` | Лимит на IP: 5 запросов / 10 минут |
| `CORS_ORIGINS` | Через запятую, `*` не поддерживается сознательно |

### Деплой

Готов `render.yaml` — на Render'е достаточно подключить репозиторий, задать
секреты (`OPENROUTER_API_KEY`, SMTP-креды, `OWNER_EMAIL`) и нажать Deploy.

## Стек

**Backend**
- Python 3.12+
- FastAPI + Uvicorn (ASGI)
- Pydantic v2 — валидация и парсинг
- Pydantic Settings — загрузка `.env`
- aiosmtplib — асинхронная отправка писем
- httpx — HTTP-клиент к OpenRouter
- email-validator — валидация email в pydantic

**AI**
- OpenRouter (OpenAI-совместимый API), бесплатная Llama 3.1 8B
- Прописан fallback на локальные эвристики, если API недоступен

**Хранение**
- Файловая система (JSON): rate limit + метрики
- Ротационные логи в `storage/logs/`

Почему такой набор:

- **FastAPI** — быстрая разработка, автоматический Swagger из аннотаций, встроенная
  валидация через Pydantic, из коробки async — важно для сетевых I/O (SMTP + LLM).
- **OpenRouter вместо OpenAI/Anthropic** — единый OpenAI-совместимый API к десяткам
  провайдеров, есть бесплатные модели, тестовое задание не требует боевого качества
  ответов.
- **Файлы вместо БД** — задание допускает, а для 3–4 счётчиков и rate limit
  тащить Postgres/Redis нет смысла. Уровень доступа к данным изолирован в
  `repositories/`, при желании подмена на БД — точечная.

## Архитектура

Слоистая: контроллеры → сервисы → репозитории. Инфраструктура (config, logging,
errors) вынесена в `core/`.

```
app/
├── api/                  # роутеры FastAPI
│   ├── contact.py        #   POST /api/contact
│   ├── health.py         #   GET  /api/health
│   └── metrics.py        #   GET  /api/metrics
├── services/             # бизнес-логика
│   ├── contact.py        #   оркестрация: AI + email + метрики
│   ├── ai.py             #   вызов OpenRouter + fallback
│   ├── email.py          #   отправка через SMTP, HTML+text
│   ├── email_templates.py#   шаблоны писем (owner + user)
│   └── rate_limit.py     #   dependency для FastAPI
├── repositories/         # доступ к данным
│   ├── rate_limit.py     #   JSON: IP → [timestamps]
│   └── metrics.py        #   JSON: агрегированные счётчики
├── schemas/              # pydantic-модели request/response
│   ├── contact.py        #   ContactRequest / ContactResponse / ContactAiInsights
│   ├── health.py         #   HealthResponse
│   └── metrics.py        #   MetricsResponse
├── core/                 # инфраструктура
│   ├── config.py         #   pydantic-settings
│   ├── enums.py          #   ContactCategory / Sentiment / InsightSource
│   ├── errors.py         #   глобальные exception handlers
│   ├── logging.py        #   file logger + request middleware
│   └── utils.py          #   client_ip / utcnow_iso
├── static/               # лендинг с формой
│   └── index.html
└── main.py               # сборка приложения (create_app + middleware + routers)

storage/                  # файловое хранилище (в .gitignore)
├── logs/                 #   app.log (rotating), requests.log (rotating JSONL)
├── metrics.json
└── rate_limit.json

tests/                    # pytest + FastAPI TestClient
├── conftest.py           #   изоляция хранилища + мок SMTP/AI
├── test_contact_validation.py
├── test_ai_fallback.py
├── test_health_and_metrics.py
└── test_rate_limit.py
```

Основные решения:

- **Оркестратор в сервисе, не в контроллере.** `api/contact.py` только читает тело
  и request_id, дальше вся логика в `services/contact.py`. Контроллер тонкий,
  сервис легко тестируется.
- **Rate limit — FastAPI-dependency.** Прописан на эндпоинте `/api/contact`
  через `Depends`, легко подключить к другим эндпоинтам, не размазан по контроллеру.
- **Файловые репозитории под `asyncio.Lock`.** Атомарная запись через `tmp → replace`,
  чтобы не поймать наполовину записанный JSON при аварии.
- **Единый `AppError` + подтипы.** `RateLimitError`, `EmailSendError` уносят наверх
  свои HTTP-коды. Глобальный handler превращает всё в единый JSON-формат:
  ```json
  { "error": { "code": "...", "message": "..." }, "request_id": "..." }
  ```
- **`x-request-id` в каждом ответе.** Middleware генерирует ID, кладёт в
  `request.state`, добавляет в заголовок и пишет в лог запросов.

## API

Полная спецификация — Swagger UI по `/docs`. Ниже — сжато.

### `POST /api/contact`

Приём заявки. Валидирует, применяет rate limit, вызывает AI, отправляет два письма
(владельцу + пользователю), пишет в метрики.

**Запрос:**

```bash
curl -X POST http://localhost:8000/api/contact \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Иван Петров",
    "email": "ivan@example.com",
    "phone": "+7 999 123-45-67",
    "comment": "Ищу backend-разработчика на проект, готов обсудить бюджет и сроки."
  }'
```

**Ответ 200:**

```json
{
  "ok": true,
  "request_id": "b371daffcfae",
  "insights": {
    "category": "project",
    "sentiment": "neutral",
    "reply_draft": "Здравствуйте, Иван! Спасибо за обращение...",
    "source": "ai"
  },
  "message": "Спасибо, ваша заявка принята."
}
```

**Валидация:**

- `name` — 2–100 символов
- `email` — RFC-валидный
- `phone` — 6–32 символа, только цифры/`+`/`-`/пробелы/скобки, 6–15 цифр
- `comment` — 5–2000 символов

**Возможные ошибки:**

| Код | Когда |
|---|---|
| 422 | `validation_error` — не прошли поля, в `details` — какие именно (сообщения локализованы, см. ниже) |
| 429 | `rate_limited` — превышен лимит запросов с IP |
| 502 | `email_failed` — не удалось доставить письмо владельцу |
| 500 | `internal_error` — всё остальное |

**Локализация сообщений валидации.** Pydantic по умолчанию отдаёт тексты
на английском (`Field required`, `String should have at least N characters`,
`value is not a valid email address …`). Глобальный `RequestValidationError`
handler в `app/core/errors.py::_translate_validation_error` мапит их на
русский по типу ошибки:

| Pydantic `type` | Ответ клиенту |
|---|---|
| `missing` | `поле обязательно` |
| `string_too_short` | `не короче N символов` |
| `string_too_long` | `не длиннее N символов` |
| `string_type` | `ожидается строка` |
| `value_error` (EmailStr) | `некорректный email` |
| `value_error` (custom) | текст из моего валидатора, префикс `Value error,` срезается |
| `json_invalid` / `json_type` | `некорректный JSON` |

Пример ответа при пустом теле:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Проверьте корректность введённых данных",
    "details": [
      { "field": "name",    "message": "поле обязательно" },
      { "field": "email",   "message": "поле обязательно" },
      { "field": "phone",   "message": "поле обязательно" },
      { "field": "comment", "message": "поле обязательно" }
    ]
  },
  "request_id": "3df4fe619810"
}
```

### `GET /api/health`

Проверка статуса. Отдаёт `ok` если SMTP и AI сконфигурированы, `degraded` если нет.

### `GET /api/metrics`

Агрегированные счётчики: всего запросов, успешных/провальных, разбивка по
категориям и тональности.

### Postman

Готовая коллекция — `postman_collection.json` (импортировать в Postman/Insomnia).
Переменная `baseUrl` — по умолчанию `http://localhost:8000`.

## AI-интеграция

Одним запросом к OpenRouter достаём JSON вида:

```json
{
  "category": "job | project | collaboration | question | spam | other",
  "sentiment": "positive | neutral | negative",
  "reply_draft": "1-3 абзаца ответа пользователю"
}
```

Черновик ответа подкладываем в письмо пользователю — это делает автоответ
персонализированным (не «спасибо, мы получили»), но остаётся под контролем
владельца (он получает копию с полным разбором и может отреагировать вручную).

**System prompt** — сжато формулирует роль и правила:

> Ты помогаешь разработчику разбирать входящие заявки с лендинга.
> Твоя задача — классифицировать обращение, определить тональность и составить
> короткий персонализированный ответ на русском языке от имени владельца сайта.
> Отвечай ТОЛЬКО валидным JSON, без комментариев и без markdown.

**User prompt** содержит все поля заявки и явную JSON-схему в самом промпте
(модель отвечает по этой форме).

**Fallback.** Если ключа нет / API вернул ошибку / таймаут / модель ответила
не-JSON — отваливаемся на локальный анализатор на ключевых словах (см.
`app/services/ai.py::_fallback`). Он даёт разумную категорию/тональность и
шаблонный ответ. В поле `source` пишем `ai` или `fallback` — видно и оценщику,
и владельцу в письме, каким путём получили инсайты.

**Устойчивость к «шумной» модели.** Парсер JSON терпит обёртку в
` ```json ... ``` ` и мусор до/после скобок — вытаскивает первое `{...}`.

## Что делал с помощью AI при разработке

Использовал AI как помощника-автодополнение:

- **Регулярка для телефона** — попросил накидать варианты с учётом разных форматов
  (`+7 (999) 123-45-67`, `89991234567` и т.д.), выбрал минимальный, дополнил
  проверкой длины цифровой части руками.
- **HTML-темплейты писем** — сгенерил каркас с инлайновыми стилями (email-клиенты
  не любят внешний CSS), потом переписал под нужный контент.
- **Верстка лендинга** — тёмная тема и сетка формы. По мелочам подгонял руками
  (пробелы, breakpoint, ошибки под полями).

Архитектуру, разбиение на слои, обработку ошибок, промпт для AI и fallback-логику
писал сам. Проверял всё: и типы, и async-семантику, и что pydantic валидатор
возвращает нужное сообщение.

## Хранение данных

Задание допускает файловую систему, поэтому:

**Логи запросов** — `storage/logs/requests.log`, JSONL по строке на запрос:

```json
{"ts":"...","id":"b371da...","method":"POST","path":"/api/contact","status":200,"ip":"1.2.3.4","ua":"...","ms":1420.5}
```

Пишутся из middleware после ответа, чтобы попал реальный статус.
Дополнительно — общий лог приложения `storage/logs/app.log` (rotating, 2 МБ × 3).

**Rate limit** — `storage/rate_limit.json`. Ключ `contact:<ip>` → список timestamps.
При каждом запросе выкидываем всё, что старше окна, и решаем — пустить или отказать.
Устаревшие ключи чистятся заодно, чтобы файл не пух.

**Метрики** — `storage/metrics.json`. Счётчики:

- `total_requests`, `successful`, `failed`
- `by_category`, `by_sentiment` — словари категория/тональность → счётчик
- `last_request_at`

Пишется через `asyncio.Lock` и атомарный `tmp → replace`, чтобы не оставить
половину JSON при неожиданном падении.

**Почему не БД.** Для трёх счётчиков и одного словаря rate limit это оверкилл.
Слой репозиториев изолирован — при желании подмена на Postgres/Redis сводится
к двум файлам в `app/repositories/`.

## Тесты

Базовый набор pytest (16 тестов):

```bash
pip install -r requirements-dev.txt
pytest
```

Покрывают:

- Валидацию `/api/contact` (валидные и невалидные варианты каждого поля).
- Проброс клиентского `X-Request-Id` из заголовка запроса в заголовок ответа.
- Rate limit (403 после N попыток).
- `/api/health`, `/api/metrics` (в т.ч. инкремент после успешной заявки).
- AI-фолбэк — детект spam / job / crash апстрима.

Фикстуры изолируют файловое хранилище (`tmp_path`) и мокают SMTP/AI, чтобы
тесты не били наружу.

## Что ещё стоило бы сделать

- Retry с экспоненциальным backoff для SMTP и AI-вызова.
- Замена файлового rate limit на Redis при переезде за один инстанс.
- Метрика latency AI-вызова + счётчик fallback vs ai.

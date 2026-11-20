# Гриб

Система мониторинга, аналог Grafana: подключается к базам данных компании
(PostgreSQL, MySQL, SQLite) **только на чтение** и превращает таблицы в живые
графики. Один клиент работает в браузере, на компьютере (Electron) и на
телефоне (Capacitor), все данные берёт с одного сервера.

## Быстрый старт (Docker)

```bash
docker compose up --build
```

* веб-версия: <http://localhost:8000>, вход `admin` / `admin` — смените пароль в «Настройках»;
* демо-база магазина (PostgreSQL) с генератором данных: `localhost:5433`, база `shop`,
  пользователь только для чтения `grib_reader` / `reader`.
  В «Гриб» её подключают как источник с адресом `demo-db`, портом `5432`.

Перед реальным запуском задайте в `.env` `GRIB_SECRET_KEY` (длинная случайная строка),
`GRIB_ADMIN_PASSWORD` и `GRIB_DB_PASSWORD`. Ключ `GRIB_SECRET_KEY` шифрует пароли
источников, поэтому после первого запуска его нельзя менять.

## Разработка без Docker

```bash
# сервер
cd server
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload          # http://localhost:8000, своя БД — server/grib.db (SQLite)
.venv/bin/python -m pytest -q                    # тесты

# демо-данные в SQLite (источник: тип SQLite, файл shop.db)
python3 demo/generator.py --sqlite demo/data/shop.db
```

Клиент лежит в `client/www` и раздаётся самим сервером, сборка не нужна.

```bash
cd client && npm install
npm run desktop          # Electron
npm run android:init     # один раз: создать проект Android (нужен Android SDK)
npm run android:sync && npm run android:open
```

В desktop- и Android-версии адрес сервера указывается на экране входа.

## Устройство

```
server/app/
  routers/       HTTP API (/api/...) и WebSocket (/ws)
  schemas/       Pydantic-схемы (DTO)
  services/      бизнес-логика
  repositories/  доступ к собственной БД
  models/        таблицы SQLAlchemy
  core/          connector, query_guard, time_macros, normalizer, crypto,
                 event_bus, scheduler, executor, security, permissions,
                 schema_inspector, query_builder
client/www/      SPA: js/views — экраны, js/panels.js — фабрика графиков,
                 js/builder.js — билдер запросов, js/ws.js — WebSocket
demo/            генератор тестовых данных и SQL демо-БД
```

Документация API: <http://localhost:8000/api/docs>.

### Запросы

* Разрешены только одиночные `SELECT` / `WITH … SELECT`. Кроме того, соединение с базой
  открывается в режиме только чтения, с ограничением времени (`GRIB_QUERY_TIMEOUT`)
  и числа строк (`GRIB_QUERY_MAX_ROWS`).
* Макросы: `$from`, `$to` — границы выбранного периода (UTC), `$interval` — рекомендуемый шаг в секундах.
* Результат приводится к виду «серия — точки»: столбец `time` (или первый столбец с датой) — ось времени,
  числовые столбцы — серии, текстовые — метки, которые входят в имя серии.
  Без столбца времени запрос даёт «снимок» на текущий момент.

### Права

Роль — набор прав внутри проекта. Встроенные роли: «Владелец проекта», «Редактор»,
«Наблюдатель»; администратор может создавать свои роли. Администратор системы
(`is_admin`) имеет все права во всех проектах. Создавать проекты могут администраторы
и пользователи с флагом «Может создавать проекты».

### Переменные окружения сервера

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `GRIB_DATABASE_URL` | `sqlite:///server/grib.db` | собственная БД |
| `GRIB_SECRET_KEY` | ключ для разработки | подпись токенов и шифрование паролей источников |
| `GRIB_ADMIN_LOGIN` / `GRIB_ADMIN_PASSWORD` | `admin` / `admin` | первый администратор (создаётся, если пользователей нет) |
| `GRIB_QUERY_TIMEOUT` | `10` | лимит времени запроса к источнику, с |
| `GRIB_QUERY_MAX_ROWS` | `10000` | лимит строк результата |
| `GRIB_QUERY_POOL_SIZE` | `8` | размер пула потоков для запросов к источникам |
| `GRIB_SQLITE_DIR` | `demo/data` | каталог, вне которого SQLite-файлы открывать нельзя |
| `GRIB_MIN_COLLECTOR_INTERVAL` | `5` | минимальный интервал сборщика, с |
| `GRIB_SAMPLE_RETENTION_DAYS` | `30` | сколько дней хранить замеры |
| `GRIB_TOKEN_TTL_MINUTES` | `720` | срок жизни токена входа |

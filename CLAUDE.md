# CLAUDE.md

Навигация по репозиторию для Claude Code. Язык проекта — русский: комментарии,
docstring, весь пользовательский текст пишутся по-русски.

## Что это

4CASTER — система поддержки решения «идти в горы или нет»: мультимодельный
консенсус прогноза осадков + честная оценка надёжности + уведомления об
изменениях. Доставка — Telegram-бот и Mini App.

## PRD vs. код — читать обязательно

- **[PRD.md](PRD.md) — единственный источник **требований** (цель), а не описание
  текущего кода.** Он описывает полный MVP (30+ локаций, 5 моделей + 2 ансамбля,
  downscaling, калиброванный Reliability Score, Accuracy Engine, verification и
  т.д.). Значительная часть этого ещё **не реализована**.
- **Код — тонкий вертикальный срез, доросший до маленького живого продукта.**
  Реально сделано: 22 опубликованные локации (каталог §7.3, координаты сверены
  с DEM), 5 детерминированных моделей + 2 ансамбля через Open-Meteo, консенсус
  по единому пулу членов, надёжность A/E/S, орографическая коррекция
  температуры и фаза осадков, упрощённый HIL, детекция изменений, подписки,
  уведомления, бот + Mini App на Vercel, read-модель и архив ERA5 в Supabase
  Postgres, конвейер в GitHub Actions.
- **Не выравнивай код под PRD и PRD под код по своей инициативе.** Расхождение
  оформляется как ADR в [docs/adr/](docs/adr/) (см. правило в шапке PRD).
  Осознанно отложенное помечено в docstring словами «Фаза 2/3» и ссылками на §PRD.

## Команды

```bash
pip install -e ".[dev]"                     # установка + dev (pytest)

python -m fourcaster.cli                     # живой прогон: Ачишхо + Аибга → карточки
python -m fourcaster.cli --offline           # из фикстур tests/fixtures (без сети)
python -m fourcaster.cli achishkho -d 5      # одна локация, 5 суток
python -m fourcaster.cli achishkho --save    # + запись в Postgres и рассылка алертов

pytest                                       # тесты; все offline, без сети
python -m fourcaster.platform.db             # health-check подключения к БД (пароль не логируется)

alembic upgrade head                         # миграции (через Session pooler :5432)
python scripts/telegram_webhook.py set https://<app>.vercel.app/api/telegram
python scripts/telegram_webhook.py info      # | delete

python scripts/verify_locations.py --snap    # сверка каталога с DEM (задача 0.3)
python scripts/backfill_archive.py           # архив ERA5 + пересборка σ_clim (1.7)
python scripts/backfill_archive.py --report  # только полнота архива
```

На Windows `alembic` и скрипты печатают юникод — при проблемах с консолью
ставь `PYTHONIOENCODING=utf-8`.

Тесты в CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) гоняются на
каждый push/PR. Все тесты **offline** — не добавляй сетевых обращений в тесты.

## Архитектура

Модульный монолит по bounded-контекстам PRD §11; src-layout, пакет `fourcaster`.
Композиционный корень конвейера — [src/fourcaster/cli.py](src/fourcaster/cli.py).

```
src/fourcaster/
  shared_kernel/     geo.py (Location/Coordinate + dem_elevation_m), variables.py
  modules/
    locations/       seed-каталог CATALOG (33 точки §7.3, 22 опубликованы)
    ingestion/        порт ForecastProvider (ports.py) + адаптер Open-Meteo (ACL)
                        infrastructure/openmeteo/ — схемы внешнего API живут ТОЛЬКО здесь;
                        в клиенте лимитер/ретраи/предохранитель (задача 1.2)
    forecasting/      normalize.py — Raw*Series → ModelSnapshot / EnsembleSnapshot
    consensus/        models.py (MODELS + ENSEMBLES + guardrails весов),
                        calculator.py (пул членов §10.5.1, перцентили, POP)
    downscaling/      correct.py — остаточная коррекция T, изотерма, фаза осадков (§10.3)
    reliability/      score.py — компоненты A/E/S и свёртка (§10.6),
                        climatology.py + data/sigma_clim.json (σ_clim из архива)
    hazard/           rain.py — HIL по суточной сумме (срезовая эвристика)
    changedetection/  detect.py — значимые изменения vs. прошлый прогон (анти-флаппинг)
    notification/     alerts.py — форматирование и рассылка алертов подписчикам
    telegram_ui/      bot.py (aiogram 3 handlers), service.py (логика ответов без транспорта),
                        keyboards.py, renderers.py (карточка), webapp.py (FastAPI/ASGI),
                        miniapp_page.py (HTML Mini App одной строкой)
  platform/          config.py (env), db.py (движок), models.py (ORM read-модель + архив),
                       read_model.py (проекции: карточки, история, подписки)
api/index.py         точка входа Vercel — экспортирует ASGI `app` из webapp.py
scripts/             verify_locations.py (сверка каталога с DEM, задача 0.3),
                       backfill_archive.py (архив ERA5 + σ_clim, задача 1.7),
                       telegram_webhook.py
```

### Поток данных (конвейер §10.1, срезовое подмножество)

`cli.py` → Open-Meteo (5 моделей + 2 ансамбля, два запроса) → `normalize` →
`build_pools` (единый взвешенный пул членов §10.5.1) → `consensus_from_pool`
(p10/p25/p50/p75/p90 + POP) → `build_profile` (изотерма, фаза осадков) →
`compute_reliability` (A/E/S) → `classify_hil` → рендер карточки. С `--save`:
`get_recent_series` (история для компоненты S) → `upsert_card` (read-модель) +
`insert_history` (эволюция) + `detect_changes` vs. прошлый прогон →
`send_alerts` подписчикам.

Продакшн-конвейер — [.github/workflows/pipeline.yml](.github/workflows/pipeline.yml)
по cron 6×/сутки (02/06/10/14/18/22 UTC, §11.5), запускает `cli.py --save`.

### Доставка

- **Бот** (aiogram 3): webhook на Vercel. `api/index.py` → `webapp.py` (`app`).
  Обработчики только транспортные, логика в `service.py`, читает готовые карточки
  из read-модели (не пересчитывает). Команды: `/start`, `/help`, `/forecast [id]`,
  `/locations`, `/my`; инлайн-кнопки локаций, подписки, легенды, кнопка Mini App.
- **Mini App**: `GET /app` отдаёт HTML; фронт тянет `/api/locations`,
  `/api/forecast`, `/api/hourly` (живой запрос к Open-Meteo), `/api/history`
  (heatmap эволюции из БД). Webhook — `POST /api/telegram` (или `/`).

## Инварианты и подводные камни

- **Модель ≠ транспорт (§8.1.2).** `ForecastModel` — носитель метео-независимости,
  получает вес; `openmeteo_id` — идентификатор транспорта. Модель учитывается в
  консенсусе один раз (INV-4). Не добавляй «модель», которая на деле дублирует IFS.
- **`None` в осадках ≠ 0.** `None` = «модель не покрывает этот день» (за горизонтом
  выпуска); такой день исключается из пула, а не считается сухим. Не подменяй нулём.
- **Тип агрегации переменной важен:** осадки — `accumulated`, температура/CAPE —
  `instant`. Путаница здесь — типовой дефект (§10.2).
- **Снапшоты/консенсус иммутабельны** (INV-1..3); новый прогон = новая запись/строка
  истории (append-only по PK `(location, issued_at, valid_date)`).
- **Read-модель, а не пересчёт на запрос.** Бот и Mini App отдают закэшированную
  карточку (FR-TG-7, ответ ≤2 с). Пересчёт — только в конвейере/`--save`.
- **HIL сейчас — эвристика по p50 суточной суммы** ([hazard/rain.py](src/fourcaster/modules/hazard/rain.py)).
  Полный HIL (интенсивность, конвекция, CAPE, время суток, высота, сухие окна) —
  Фаза 2.
- **Надёжность считается в домене** ([reliability/](src/fourcaster/modules/reliability/)),
  а UI её только показывает. Наружу идёт **слово, а не число** (INV-6: калибровки
  по факту ещё нет). В JS Mini App остался запасной расчёт по разбросу — он для
  карточек, записанных до появления модуля; удалять его можно, когда в кэше не
  останется старых.
- **Ансамбль ≠ ещё один голос модели.** Вес ансамбля делится между его членами
  (§10.5.1), иначе 51 член IFS ENS перевесил бы всё остальное. Ограничители
  §10.5.3 проверяются при импорте `consensus/models.py`.
- **Downscaling делает провайдер, мы — только остаток.** Open-Meteo сам приводит
  температуру к переданному `elevation` с Γ=0.0065; своя поправка считается от
  высоты, которую он **вернул** в ответе (FR-DS-2). Иначе коррекция удваивается.
- **`k_oro` (усиление осадков рельефом) намеренно не реализован** — PRD §10.3
  требует не подбирать формулу, а обучать множитель по факту (Фаза 3).

## Инфраструктура (ADR-0013 — serverless без карты)

- **БД:** Supabase Postgres. Рантайм — **Transaction pooler, порт 6543**
  (`make_engine`: NullPool + `prepare_threshold=None`, т.к. pgbouncer в
  transaction-режиме несовместим с server-side prepared statements). Миграции —
  **Session pooler, порт 5432** (`database_url_direct` выводит его из DATABASE_URL).
  Прямой хост `db.<ref>.supabase.co` IPv6-only — не использовать.
- **Vercel** (`@vercel/python`, [vercel.json](vercel.json)) ищет переменную `app`
  на верхнем уровне `api/index.py` — сохраняй top-level `app`. Mini App отдаётся
  **строкой** (не файлом), чтобы гарантированно попасть в бандл.
- **Секреты:** только через env / GitHub Secrets / Vercel env; никогда в git и не
  в логи (`safe_dsn` для вывода DSN). Шаблон — [.env.example](.env.example).
- **Serverless-инстанс бота «замораживается»** между запросами — держать пул
  соединений нельзя (`nullpool=True`).

## Конвенции

- Python 3.11+, `from __future__ import annotations`, dataclasses
  `frozen=True, slots=True`, type hints.
- Схемы внешних API — только в `modules/*/infrastructure/<provider>/schemas.py`,
  в домен не проникают (ACL, MB-3).
- Пользовательский текст, ошибки, коммиты — по-русски. Формат коммитов:
  `type(scope): описание` (напр. `feat(miniapp): …`, `fix(bot): …`).
- Windows-консоль по умолчанию cp1251 и не печатает emoji — `cli.py` принудительно
  переключает потоки на UTF-8.

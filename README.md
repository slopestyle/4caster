# 4CASTER

Система поддержки принятия решений о выходе в горы: мультимодельный консенсус
прогноза осадков + честная оценка надёжности + уведомления об изменениях.
Доставка — Telegram-бот и Mini App.

См. [PRD.md](PRD.md) — единственный источник **требований** (цель MVP), и
[CLAUDE.md](CLAUDE.md) — навигация по коду.

## Статус: живой вертикальный срез

Реализован сквозной сценарий конвейера PRD §10.1 и доведён до маленького
работающего продукта. Что есть сейчас:

- **2 локации** (Ачишхо, Аибга; кластер CL-ALP-W) — подмножество каталога §7.3;
- **5 детерминированных моделей** (IFS, ICON, GFS, GEM, ARPEGE) через Open-Meteo;
- **консенсус** — взвешенные перцентили p10/p50/p90 + вероятность осадков (POP);
- **HIL** (Hiking Impact Level) — упрощённая эвристика по суточной сумме;
- **детекция изменений** прогноза и **push-уведомления** подписчикам;
- **Telegram-бот** (aiogram 3) + **Mini App** (список точек, недельный прогноз,
  метеограмма 48 ч, heatmap эволюции прогноза, надёжность по разбросу моделей);
- **read-модель** в Supabase Postgres; **конвейер** в GitHub Actions по расписанию.

```
Open-Meteo (5 моделей) → нормализация → взвешенный консенсус → HIL
        → карточка (read-модель) → бот/Mini App
        → детекция изменений → алерты подписчикам
```

Это **не** полный MVP из PRD. Осознанно упрощено/отложено (Фаза 2+): орографический
downscaling (§10.3), калиброванный Reliability Score + калибровка (§10.6), ансамбли,
Accuracy Engine и верификация по ground truth (§8.4), полный HIL (§10.4), остальные
локации каталога (§7.3). Полный план — PRD §19.

## Запуск

```bash
python -m pip install -e ".[dev]"        # установка + pytest

python -m fourcaster.cli                 # живой запрос к Open-Meteo, Ачишхо + Аибга
python -m fourcaster.cli --offline       # из записанных фикстур (tests/fixtures)
python -m fourcaster.cli achishkho -d 5  # одна локация, горизонт 5 суток
python -m fourcaster.cli achishkho --save  # + запись в Postgres и рассылка алертов
pytest                                   # тесты (offline, без сети)
```

## Структура (подмножество PRD §11.3)

```
src/fourcaster/
  shared_kernel/    geo.py, variables.py — каноническое ядро
  modules/
    locations/       seed-каталог (Ачишхо, Аибга)
    ingestion/        порт ForecastProvider + адаптер Open-Meteo (ACL)
    forecasting/      нормализация к канонической схеме
    consensus/        реестр моделей + взвешенные перцентили, POP
    hazard/           RainHazard: упрощённый HIL
    changedetection/  значимые изменения vs. прошлый прогон
    notification/     форматирование и рассылка алертов
    telegram_ui/      бот (aiogram 3), FastAPI-webhook, Mini App, рендер карточки
  platform/          config, движок БД, ORM read-модель, проекции
  cli.py             композиционный корень среза
api/index.py         точка входа Vercel (ASGI app)
```

Подробнее об инвариантах, потоках данных и подводных камнях — [CLAUDE.md](CLAUDE.md).

## Хостинг и деплой

Развёртывание — бесплатный serverless без верификации картой (замена Oracle из
§16). Решение: [ADR-0013](docs/adr/ADR-0013-hosting-serverless-no-card.md).

- **Конвейер** — GitHub Actions по циклам §11.5, 6 прогонов/сутки
  ([pipeline.yml](.github/workflows/pipeline.yml)): `cli.py --save` пишет карточки и
  историю в Postgres и рассылает алерты. Запуск вручную: Actions → *Forecast
  pipeline* → Run.
- **БД** — Supabase Postgres. Рантайм через Transaction pooler (`:6543`), миграции
  Alembic через Session pooler (`:5432`) — см. [supabase-connection](CLAUDE.md).
- **Бот + Mini App** — webhook на Vercel (Python/ASGI, aiogram 3).
- **CI** — [ci.yml](.github/workflows/ci.yml): `pytest` на каждый push/PR.

### Telegram-бот

Webhook на Vercel читает готовые карточки из read-модели (FR-TG-7). Команды:
`/start`, `/help`, `/forecast [id]`, `/locations`, `/my` + инлайн-кнопки локаций,
подписок и кнопка Mini App. Код: [modules/telegram_ui/](src/fourcaster/modules/telegram_ui/),
ASGI-обёртка [webapp.py](src/fourcaster/modules/telegram_ui/webapp.py), точка входа
Vercel [api/index.py](api/index.py).

Деплой:
1. Импортировать репозиторий в Vercel (регистрация без карты).
2. В Vercel → Settings → Environment Variables задать `DATABASE_URL` (pooler `:6543`),
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`.
3. После деплоя привязать webhook:
   ```bash
   python scripts/telegram_webhook.py set https://<app>.vercel.app/api/telegram
   python scripts/telegram_webhook.py info
   ```

## Атрибуция

Источники (CC BY 4.0): данные Open-Meteo и первоисточников —
DWD (ICON), NOAA (GFS), ECMWF (IFS), ECCC (GEM), Météo-France (ARPEGE).

# 4CASTER

Система поддержки принятия решений о выходе в горы: мультимодельный консенсус
прогноза осадков + честная оценка надёжности + уведомления об изменениях.
Доставка — Telegram-бот и Mini App.

См. [PRD.md](PRD.md) — единственный источник **требований** (цель MVP), и
[CLAUDE.md](CLAUDE.md) — навигация по коду.

## Статус: живой вертикальный срез

Реализован сквозной сценарий конвейера PRD §10.1 и доведён до маленького
работающего продукта. Что есть сейчас:

- **22 локации** из каталога §7.3, координаты сверены с DEM ([ADR-0017](docs/adr/ADR-0017-dem-verification-policy.md));
  ещё 11 точек — черновики: высота сошлась, привязка к ориентиру нет (FR-LOC-5);
- **5 детерминированных моделей** (IFS, ICON, GFS, GEM, ARPEGE) **и 2 ансамбля**
  (ECMWF IFS ENS — 51 член, NOAA GEFS — 31) через Open-Meteo;
- **консенсус** — единый взвешенный пул из 87 членов (§10.5.1): перцентили
  p10/p25/p50/p75/p90 и вероятность осадков прямо по эмпирической CDF;
- **надёжность** — компоненты A (согласие моделей), E (разброс ансамблей против
  климата), S (устойчивость прогноза от прогона к прогону). Показывается
  качественной шкалой, а не числом: калибровки по факту ещё нет (INV-6);
- **орографическая коррекция** температуры, нулевая изотерма и фаза осадков
  (снег / мокрый снег / дождь) — критично для точек выше 2500 м;
- **HIL** (Hiking Impact Level) — упрощённая эвристика по суточной сумме;
- **архив реанализа** за 2024–2026 по всем точкам: 30 756 суточных значений,
  из них посчитана климатология σ_clim;
- **детекция изменений** прогноза и **push-уведомления** подписчикам;
- **Telegram-бот** (aiogram 3) + **Mini App** (список точек, недельный прогноз,
  метеограмма 48 ч, heatmap эволюции прогноза, надёжность на 1/3/7/14 дней
  с разбором по компонентам);
- **read-модель** в Supabase Postgres; **конвейер** в GitHub Actions по расписанию.

```
Open-Meteo (5 моделей + 2 ансамбля) → нормализация → пул членов → консенсус
        → downscaling (изотерма, фаза) → надёжность (A/E/S/H, по горизонтам
          1/3/7/14 суток) → HIL
        → карточка (read-модель) → бот/Mini App
        → детекция изменений → алерты подписчикам
```

Это **не** полный MVP из PRD. Осознанно упрощено/отложено (Фаза 2+): калибровка
Reliability Score, измеренная H и компонента G (§10.6), Accuracy Engine и ground truth по
станциям (§8.4, §10.8), обучение весов и `k_oro` (§10.8.5), полный HIL (§10.4),
Trips (§6.1), резервный транспорт api.met.no (§8.3). Полный план — PRD §19,
текущий статус — PRD §0.

## Запуск

```bash
python -m pip install -e ".[dev]"        # установка + pytest

python -m fourcaster.cli                 # живой прогон по всему опубликованному каталогу
python -m fourcaster.cli --offline       # из записанных фикстур (tests/fixtures)
python -m fourcaster.cli achishkho -d 5  # одна локация, горизонт 5 суток
python -m fourcaster.cli achishkho --save  # + запись в Postgres и рассылка алертов
python -m fourcaster.cli --no-ensembles  # только детерминированное ядро (экономия квоты)
pytest                                   # тесты (offline, без сети)
```

Обслуживание данных:

```bash
python scripts/verify_locations.py          # сверка каталога с DEM (задача 0.3)
python scripts/verify_locations.py --snap   # + поиск координат для несошедшихся точек
python scripts/backfill_archive.py          # выгрузка архива ERA5 + пересборка σ_clim
python scripts/backfill_archive.py --report # только отчёт о полноте архива
```

На Windows консоль по умолчанию cp1251 — если скрипт или `alembic` падает на
печати юникода, запускайте с `PYTHONIOENCODING=utf-8`.

## Структура (подмножество PRD §11.3)

```
src/fourcaster/
  shared_kernel/    geo.py (Location + dem_elevation_m), variables.py
  modules/
    locations/       seed-каталог §7.3: 33 точки, 22 опубликованы
    ingestion/        порт ForecastProvider + адаптер Open-Meteo (ACL),
                        лимитер / ретраи / предохранитель
    forecasting/      нормализация к канонической схеме
    consensus/        реестр моделей и ансамблей + пул членов, перцентили, POP
    downscaling/      остаточная коррекция T, изотерма, фаза осадков
    reliability/      компоненты A/E/S/H, агрегация по горизонтам, σ_clim
    hazard/           RainHazard: упрощённый HIL
    changedetection/  значимые изменения vs. прошлый прогон
    notification/     форматирование и рассылка алертов
    telegram_ui/      бот (aiogram 3), FastAPI-webhook, Mini App, рендер карточки
  platform/          config, движок БД, ORM (read-модель + архив), проекции
  cli.py             композиционный корень конвейера
api/index.py         точка входа Vercel (ASGI app)
scripts/             сверка каталога, backfill архива, привязка webhook
```

Подробнее об инвариантах, потоках данных и подводных камнях — [CLAUDE.md](CLAUDE.md).

## Архитектурные решения

Расхождения с требованиями PRD оформляются как ADR в [docs/adr/](docs/adr/):

| ADR | О чём |
|---|---|
| [0013](docs/adr/ADR-0013-hosting-serverless-no-card.md) | Хостинг на бесплатном serverless без верификации картой (вместо §16) |
| [0014](docs/adr/ADR-0014-ensemble-pool-weights.md) | Ансамбли в общем пуле членов и перевзвешивание §8.2 |
| [0015](docs/adr/ADR-0015-residual-orographic-correction.md) | Остаточная орографическая коррекция: провайдер уже правит температуру сам |
| [0016](docs/adr/ADR-0016-reliability-aes-and-era5-source.md) | Надёжность на A/E/S и ERA5 seamless как источник архива |
| [0017](docs/adr/ADR-0017-dem-verification-policy.md) | Сверка каталога по DEM: понижаем уверенность, но не повышаем |

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
DWD (ICON), NOAA (GFS и GEFS), ECMWF (IFS и IFS ENS), ECCC (GEM),
Météo-France (ARPEGE). Архив реанализа и высоты рельефа: ERA5 / ERA5-Land
(Copernicus Climate Change Service) и Copernicus DEM GLO-90.

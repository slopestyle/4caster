# 4CASTER

Система поддержки принятия решений о выходе в горы. См. [PRD.md](PRD.md) —
единственный источник требований.

## Статус: vertical slice (тонкий сквозной срез)

Реализован один сценарий конвейера PRD §10.1 для проверки стека и границ
модулей — **прогноз по Ачишхо и Аибге**:

```
Open-Meteo (5 моделей) → нормализация → взвешенный консенсус → HIL → карточка
```

Это **не** MVP. Полный план — PRD §19. Осознанно упрощено/отложено:
downscaling (§10.3), Reliability Score + калибровка (§10.6, Фаза 2),
ансамбли, change detection, БД/Redis/очереди, aiogram-бот и графика.

## Запуск

```bash
python -m pip install -e .            # или: pip install httpx pydantic numpy pytest
python -m fourcaster.cli              # живой запрос к Open-Meteo, Ачишхо + Аибга
python -m fourcaster.cli --offline    # из записанных фикстур (tests/fixtures)
python -m fourcaster.cli achishkho -d 5
pytest                                # 6 тестов (offline, без сети)
```

## Структура (подмножество PRD §11.3)

```
src/fourcaster/
  shared_kernel/          geo.py, variables.py — каноническое ядро
  modules/
    locations/            seed-каталог (Ачишхо, Аибга; кластер CL-ALP-W)
    ingestion/            порт ForecastProvider + адаптер Open-Meteo (ACL)
    forecasting/          нормализация к канонической схеме
    consensus/            реестр моделей + взвешенные перцентили, POP
    hazard/               RainHazard: упрощённый HIL
    telegram_ui/          рендер карточки §15.3 (только отображение)
  cli.py                  композиционный корень среза
```

## Хостинг

Развёртывание — бесплатный serverless без верификации картой (замена Oracle
из §16). Решение: [ADR-0013](docs/adr/ADR-0013-hosting-serverless-no-card.md).

- **Конвейер** — GitHub Actions по расписанию циклов §11.5
  ([pipeline.yml](.github/workflows/pipeline.yml)); сейчас гоняет срез и кладёт
  карточки в артефакт. Запуск вручную: вкладка Actions → *Forecast pipeline* → Run.
- **БД** — Supabase/Neon Postgres (по мере роста). **Бот** — Vercel/Deno webhook.
- **CI** — [ci.yml](.github/workflows/ci.yml): `pytest` на каждый push/PR.

## Атрибуция

Источники (CC BY 4.0): данные Open-Meteo и первоисточников —
DWD (ICON), NOAA (GFS), ECMWF (IFS), ECCC (GEM), Météo-France (ARPEGE).

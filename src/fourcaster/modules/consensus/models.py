"""Реестр численных моделей и стартовых весов (PRD §8.2).

`ForecastModel` — носитель метеорологической независимости; только он
получает вес в консенсусе (INV-4: одна модель учитывается не более
одного раза). `openmeteo_id` — идентификатор транспорта Open-Meteo (T1),
не путать с доменной моделью (разделение «Модель»/«Транспорт», §8.1.2).

`EnsembleModel` — ансамбль (§8.2 E1–E2). Его вес делится поровну между
членами: ансамбль из 51 члена не должен перевешивать пять детерминированных
моделей числом (§10.5.1). Ансамбль и его детерминированный «брат» (IFS ENS и
IFS HRES — одна система) коррелированы, поэтому §10.5.3 ограничивает их
совместный вес; проверку держит `_check_guardrails` ниже.

Веса — стартовые (§8.2); в MVP пересчитываются Accuracy Engine (Фаза 3).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ForecastModel:
    id: str
    name: str
    center: str
    weight: float          # стартовый вес консенсуса (§8.2)
    openmeteo_id: str      # идентификатор модели в Open-Meteo API


@dataclass(frozen=True, slots=True)
class EnsembleModel:
    id: str
    name: str
    center: str
    weight: float          # вес ансамбля целиком; член получает weight / N
    openmeteo_id: str      # как называть в параметре `models` запроса
    response_key: str      # как ансамбль назван в ключах ответа (это не одно и то же)
    n_members: int         # ожидаемое число членов (контрольный + возмущённые)
    sibling_id: str | None = None   # детерминированная модель той же системы


# Детерминированное ядро. Веса — доли §8.2, ужатые до 0.60: остальные 0.40
# отданы ансамблям, которые несут вероятностную информацию (§8.2, E1–E2).
MODELS: tuple[ForecastModel, ...] = (
    ForecastModel("ifs", "ECMWF IFS", "ECMWF", 0.175, "ecmwf_ifs025"),
    ForecastModel("icon", "DWD ICON", "DWD", 0.165, "icon_global"),
    ForecastModel("gfs", "NOAA GFS", "NCEP", 0.115, "gfs_global"),
    ForecastModel("gem", "ECCC GEM", "ECCC", 0.095, "gem_global"),
    ForecastModel("arpege", "MF ARPEGE", "Météo-France", 0.05, "meteofrance_arpege_world"),
)

# E3 (ICON-EPS) — Фаза 2 по §8.2, здесь сознательно нет.
ENSEMBLES: tuple[EnsembleModel, ...] = (
    EnsembleModel("ifs_ens", "ECMWF IFS ENS", "ECMWF", 0.25,
                  "ecmwf_ifs025", "ecmwf_ifs025_ensemble", 51, sibling_id="ifs"),
    EnsembleModel("gefs", "NOAA GEFS", "NCEP", 0.15,
                  "gfs025", "ncep_gefs025", 31, sibling_id="gfs"),
)

BY_OPENMETEO_ID: dict[str, ForecastModel] = {m.openmeteo_id: m for m in MODELS}
BY_RESPONSE_KEY: dict[str, EnsembleModel] = {e.response_key: e for e in ENSEMBLES}


def _check_guardrails() -> None:
    """Ограничители §10.5.3 — нарушение ловим при импорте, а не в проде.

    Через `raise`, а не `assert`: под `python -O` проверки-ассерты исчезают, а
    это инвариант, а не отладка.
    """
    total = sum(m.weight for m in MODELS) + sum(e.weight for e in ENSEMBLES)
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"сумма весов {total} ≠ 1 (INV-3)")
    ens_total = sum(e.weight for e in ENSEMBLES)
    if ens_total > 0.45:
        raise ValueError(f"суммарный вес ансамблей {ens_total} > 0.45")
    for member in (*MODELS, *ENSEMBLES):
        if not 0.05 <= member.weight <= 0.40:
            raise ValueError(f"вес {member.id} = {member.weight} вне [0.05, 0.40]")
    by_id = {m.id: m.weight for m in MODELS}
    for ens in ENSEMBLES:
        if ens.sibling_id:
            pair = ens.weight + by_id.get(ens.sibling_id, 0.0)
            if pair > 0.50:
                raise ValueError(
                    f"{ens.id} + {ens.sibling_id} = {pair} > 0.50 (коррелированы)"
                )


_check_guardrails()

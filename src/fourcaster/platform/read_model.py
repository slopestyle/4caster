"""Проекция консенсуса в read-модель карточки (PRD §13)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from fourcaster.modules.consensus.calculator import DayConsensus
from fourcaster.modules.downscaling import DayProfile
from fourcaster.modules.hazard.rain import classify_hil
from fourcaster.modules.reliability import Reliability
from fourcaster.platform.models import (
    ForecastCardCache,
    ForecastHistory,
    Subscription,
)


def _consensus_to_json(
    days: list[DayConsensus],
    reliability: list[Reliability] | None = None,
    profiles: list[DayProfile] | None = None,
) -> list[dict]:
    """Проекция консенсуса в JSON карточки.

    Надёжность кладётся сюда же, посуточно: она считается в домене (§10.6), а
    бот и Mini App обязаны только показывать готовое (FR-TG-7). Числа скора в
    выдачу не идут — INV-6 разрешает только качественную шкалу, пока нет
    калибровки; `score` оставлен для отладки и будущей калибровки.
    """
    by_day = {r.day: r for r in reliability or ()}
    by_index = list(profiles or ())
    out = []
    for i, d in enumerate(days):
        hil = classify_hil(d.p50)
        item = {
            "day": d.day.isoformat(),
            "p10": d.p10, "p50": d.p50, "p90": d.p90,
            "p25": d.p25, "p75": d.p75,
            "pop": d.pop, "n_models": d.n_models, "n_members": d.n_members,
            "hil_level": hil.level, "hil_label": hil.label,
        }
        rel = by_day.get(d.day)
        if rel is not None:
            item["reliability"] = {
                "level": rel.level,
                "label": rel.label,
                "score": rel.score,
                "is_calibrated": rel.is_calibrated,
                "agreement": rel.components.agreement,
                "ensemble": rel.components.ensemble,
                "ensemble_is_proxy": rel.components.ensemble_is_proxy,
                "stability": rel.components.stability,
                "n_members": rel.components.n_members,
                "n_history_runs": rel.components.n_history_runs,
            }
        profile = by_index[i] if i < len(by_index) else None
        if profile is not None and profile.phase is not None:
            item["temp_max_c"] = profile.temp_max_c
            item["temp_min_c"] = profile.temp_min_c
            item["freezing_level_m"] = profile.freezing_level_m
            item["precip_phase"] = profile.phase.value
        out.append(item)
    return out


def upsert_card(
    engine: Engine,
    *,
    location_id: str,
    computed_at: datetime,
    days: list[DayConsensus],
    rendered_text: str,
    reliability: list[Reliability] | None = None,
    profiles: list[DayProfile] | None = None,
) -> None:
    """Идемпотентная запись карточки (INSERT ... ON CONFLICT DO UPDATE)."""
    payload = {
        "location_id": location_id,
        "computed_at": computed_at,
        "days": len(days),
        "rendered_text": rendered_text,
        "consensus": _consensus_to_json(days, reliability, profiles),
    }
    stmt = insert(ForecastCardCache).values(**payload)
    stmt = stmt.on_conflict_do_update(
        index_elements=[ForecastCardCache.location_id],
        set_={k: stmt.excluded[k] for k in ("computed_at", "days", "rendered_text", "consensus")},
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def upcoming(days: list[dict], *, today: date | None = None) -> list[dict]:
    """Отбрасывает прошедшие дни карточки (день < сегодня по UTC).

    Карточка — снапшот прогона, а прогоны идут 6×/сутки и могут опаздывать или
    падать. Пока конвейер не отработал после полуночи, в кэше лежит вчерашний
    день — показывать его как «сегодня» нельзя ни в боте, ни в Mini App.
    Дни хранятся ISO-строками (YYYY-MM-DD), поэтому сравнение лексикографическое.
    """
    ref = (today or datetime.now(UTC).date()).isoformat()
    return [d for d in days if d.get("day", "") >= ref]


def get_card(engine: Engine, location_id: str) -> str | None:
    """Готовый текст карточки из кэша (FR-TG-7: ответ бота из read-модели)."""
    stmt = select(ForecastCardCache.rendered_text).where(
        ForecastCardCache.location_id == location_id
    )
    with engine.connect() as conn:
        return conn.execute(stmt).scalar_one_or_none()


def get_card_full(engine: Engine, location_id: str) -> dict | None:
    """Структурированная карточка для Mini App (JSON API)."""
    stmt = select(
        ForecastCardCache.computed_at,
        ForecastCardCache.days,
        ForecastCardCache.consensus,
    ).where(ForecastCardCache.location_id == location_id)
    with engine.connect() as conn:
        row = conn.execute(stmt).first()
    if row is None:
        return None
    days = upcoming(row.consensus or [])
    if not days:            # карточка протухла целиком — честнее «нет прогноза»
        return None
    return {
        "computed_at": row.computed_at.isoformat(),
        "days_count": len(days),
        "days": days,
        "n_models": days[0]["n_models"],
    }


def insert_history(
    engine: Engine, *, location_id: str, issued_at: datetime, days: list[DayConsensus]
) -> None:
    """Append строк эволюции прогноза за один цикл (идемпотентно по PK)."""
    rows = [{
        "location_id": location_id,
        "issued_at": issued_at,
        "valid_date": d.day,
        "p10": d.p10, "p50": d.p50, "p90": d.p90, "pop": d.pop,
        "hil_level": classify_hil(d.p50).level,
    } for d in days]
    if not rows:
        return
    stmt = insert(ForecastHistory).values(rows).on_conflict_do_nothing(
        index_elements=[
            ForecastHistory.location_id,
            ForecastHistory.issued_at,
            ForecastHistory.valid_date,
        ]
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def get_history(engine: Engine, location_id: str, *, max_issues: int = 14) -> dict:
    """Матрица эволюции: последние N моментов выпуска × прогнозируемые даты → p50."""
    stmt = (
        select(
            ForecastHistory.issued_at,
            ForecastHistory.valid_date,
            ForecastHistory.p50,
        )
        .where(ForecastHistory.location_id == location_id)
        .order_by(ForecastHistory.issued_at, ForecastHistory.valid_date)
    )
    with engine.connect() as conn:
        recs = conn.execute(stmt).all()

    issues = sorted({r.issued_at for r in recs})[-max_issues:]
    issue_set = set(issues)
    valid_dates = sorted({r.valid_date for r in recs})
    cell = {(r.issued_at, r.valid_date): r.p50 for r in recs if r.issued_at in issue_set}

    max_p50 = max((v for v in cell.values()), default=0.0)
    rows = [{
        "date": vd.isoformat(),
        "vals": [cell.get((iss, vd)) for iss in issues],
    } for vd in valid_dates]
    return {
        "issues": [i.isoformat() for i in issues],
        "rows": rows,
        "max": max_p50,
    }


def get_recent_series(
    engine: Engine, location_id: str, *, n_issues: int = 6
) -> dict[str, dict[str, list]]:
    """Последние N прогонов по каждой прогнозируемой дате — сырьё компоненты S.

    Возвращает {valid_date_iso: {"p50": [...], "hil": [...]}} в порядке выпуска
    прогнозов (от старого к новому). Flip-Flop Index (§10.6) считает именно по
    такой последовательности: как менялась оценка на один и тот же день.
    """
    sub = (
        select(ForecastHistory.issued_at)
        .where(ForecastHistory.location_id == location_id)
        .distinct()
        .order_by(ForecastHistory.issued_at.desc())
        .limit(n_issues)
        .scalar_subquery()
    )
    stmt = (
        select(
            ForecastHistory.valid_date,
            ForecastHistory.issued_at,
            ForecastHistory.p50,
            ForecastHistory.hil_level,
        )
        .where(
            ForecastHistory.location_id == location_id,
            ForecastHistory.issued_at.in_(sub),
        )
        .order_by(ForecastHistory.valid_date, ForecastHistory.issued_at)
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt).all()

    out: dict[str, dict[str, list]] = {}
    for row in rows:
        entry = out.setdefault(row.valid_date.isoformat(), {"p50": [], "hil": []})
        entry["p50"].append(float(row.p50))
        entry["hil"].append(int(row.hil_level))
    return out


def get_previous_snapshot(engine: Engine, location_id: str) -> dict:
    """Последний записанный прогон (для сравнения с новым): {valid_date_iso: {...}}."""
    from sqlalchemy import func
    sub = (
        select(func.max(ForecastHistory.issued_at))
        .where(ForecastHistory.location_id == location_id)
        .scalar_subquery()
    )
    stmt = select(
        ForecastHistory.valid_date, ForecastHistory.p50,
        ForecastHistory.pop, ForecastHistory.hil_level,
    ).where(
        ForecastHistory.location_id == location_id,
        ForecastHistory.issued_at == sub,
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt).all()
    return {
        r.valid_date.isoformat(): {"p50": r.p50, "pop": r.pop, "hil_level": r.hil_level}
        for r in rows
    }


# ---- подписки (US-SUB-1) ----

def subscribe(engine: Engine, chat_id: int, location_id: str) -> None:
    stmt = insert(Subscription).values(
        chat_id=chat_id, location_id=location_id
    ).on_conflict_do_nothing(
        index_elements=[Subscription.chat_id, Subscription.location_id]
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def unsubscribe(engine: Engine, chat_id: int, location_id: str) -> None:
    stmt = delete(Subscription).where(
        Subscription.chat_id == chat_id, Subscription.location_id == location_id
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def list_subscriptions(engine: Engine, chat_id: int) -> list[str]:
    stmt = select(Subscription.location_id).where(Subscription.chat_id == chat_id)
    with engine.connect() as conn:
        return [r[0] for r in conn.execute(stmt).all()]


def subscribers_for(engine: Engine, location_id: str) -> list[int]:
    stmt = select(Subscription.chat_id).where(Subscription.location_id == location_id)
    with engine.connect() as conn:
        return [r[0] for r in conn.execute(stmt).all()]


def list_cards(engine: Engine) -> dict[str, dict]:
    """Сводка по всем закэшированным локациям: {location_id: {computed_at, today}}."""
    stmt = select(
        ForecastCardCache.location_id,
        ForecastCardCache.computed_at,
        ForecastCardCache.consensus,
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt).all()
    out: dict[str, dict] = {}
    for r in rows:
        cons = upcoming(r.consensus or [])
        out[r.location_id] = {
            "computed_at": r.computed_at.isoformat(),
            "today": (cons[0] if cons else None),
            "days": cons[:8],  # для мультидневной полосы на карточке
            "days_total": len(cons),
            "n_models": (cons[0]["n_models"] if cons else 0),
        }
    return out

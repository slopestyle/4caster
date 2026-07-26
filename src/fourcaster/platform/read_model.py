"""Проекция консенсуса в read-модель карточки (PRD §13)."""

from __future__ import annotations

from datetime import datetime

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from fourcaster.modules.consensus.calculator import DayConsensus
from fourcaster.modules.hazard.rain import classify_hil
from fourcaster.platform.models import (
    ForecastCardCache,
    ForecastHistory,
    Subscription,
)


def _consensus_to_json(days: list[DayConsensus]) -> list[dict]:
    out = []
    for d in days:
        hil = classify_hil(d.p50)
        out.append({
            "day": d.day.isoformat(),
            "p10": d.p10, "p50": d.p50, "p90": d.p90,
            "pop": d.pop, "n_models": d.n_models,
            "hil_level": hil.level, "hil_label": hil.label,
        })
    return out


def upsert_card(
    engine: Engine,
    *,
    location_id: str,
    computed_at: datetime,
    days: list[DayConsensus],
    rendered_text: str,
) -> None:
    """Идемпотентная запись карточки (INSERT ... ON CONFLICT DO UPDATE)."""
    payload = {
        "location_id": location_id,
        "computed_at": computed_at,
        "days": len(days),
        "rendered_text": rendered_text,
        "consensus": _consensus_to_json(days),
    }
    stmt = insert(ForecastCardCache).values(**payload)
    stmt = stmt.on_conflict_do_update(
        index_elements=[ForecastCardCache.location_id],
        set_={k: stmt.excluded[k] for k in ("computed_at", "days", "rendered_text", "consensus")},
    )
    with engine.begin() as conn:
        conn.execute(stmt)


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
    return {
        "computed_at": row.computed_at.isoformat(),
        "days_count": row.days,
        "days": row.consensus,
        "n_models": (row.consensus[0]["n_models"] if row.consensus else 0),
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
        cons = r.consensus or []
        out[r.location_id] = {
            "computed_at": r.computed_at.isoformat(),
            "today": (cons[0] if cons else None),
            "days": cons[:8],  # для мультидневной полосы на карточке
            "days_total": len(cons),
            "n_models": (cons[0]["n_models"] if cons else 0),
        }
    return out

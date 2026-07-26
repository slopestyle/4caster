"""Проекция консенсуса в read-модель карточки (PRD §13)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from fourcaster.modules.consensus.calculator import DayConsensus
from fourcaster.modules.hazard.rain import classify_hil
from fourcaster.platform.models import ForecastCardCache


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
        out[r.location_id] = {
            "computed_at": r.computed_at.isoformat(),
            "today": (r.consensus[0] if r.consensus else None),
            "n_models": (r.consensus[0]["n_models"] if r.consensus else 0),
        }
    return out

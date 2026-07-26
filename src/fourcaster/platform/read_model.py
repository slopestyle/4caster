"""Проекция консенсуса в read-модель карточки (PRD §13)."""

from __future__ import annotations

from datetime import datetime

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

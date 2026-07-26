"""ORM read-модели (PRD §13, облегчённый CQRS §11.1).

`forecast_card_cache` — денормализованная карточка прогноза, обновляемая
проекцией по событию ConsensusComputed; бот отдаёт её без пересчёта
(FR-TG-7: ответ ≤2 с из кэша).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ForecastCardCache(Base):
    __tablename__ = "forecast_card_cache"

    location_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    days: Mapped[int] = mapped_column(Integer)
    rendered_text: Mapped[str] = mapped_column(Text)
    # список посуточных значений консенсуса (p10/p50/p90/pop/hil)
    consensus: Mapped[list] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ForecastHistory(Base):
    """Эволюция прогноза (PRD §10.7, US-HIST-1): по одной строке на
    (локация, момент выпуска прогноза, прогнозируемая дата). Append-only,
    накапливается каждым циклом — из неё строится heat-map «как менялся
    прогноз на дату X»."""

    __tablename__ = "forecast_history"

    location_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    valid_date: Mapped[date] = mapped_column(Date, primary_key=True)
    p10: Mapped[float] = mapped_column(Float)
    p50: Mapped[float] = mapped_column(Float)
    p90: Mapped[float] = mapped_column(Float)
    pop: Mapped[float] = mapped_column(Float)
    hil_level: Mapped[int] = mapped_column(Integer)

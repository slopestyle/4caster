"""ORM read-модели (PRD §13, облегчённый CQRS §11.1).

`forecast_card_cache` — денормализованная карточка прогноза, обновляемая
проекцией по событию ConsensusComputed; бот отдаёт её без пересчёта
(FR-TG-7: ответ ≤2 с из кэша).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, Integer, String, Text, func
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
    # надёжность по горизонтам 1/3/7/14 суток (§10.6.3) — то, что показывается
    # пользователю; nullable, потому что карточки старых прогонов её не имеют
    horizons: Mapped[list | None] = mapped_column(JSONB, nullable=True)
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


class ArchiveDaily(Base):
    """Архив суточных осадков по реанализу (PRD §8.4, задача 1.7 backfill).

    Это «что было на самом деле» — основа для Accuracy Engine (§10.8), порога
    значимости `NoiseFloor` (§10.9) и климатического разброса σ_clim, которым
    нормируется компонента E надёжности (§10.6). Append-only, PK
    `(location_id, valid_date)`: у одной точки за сутки один факт.
    """

    __tablename__ = "archive_daily"

    location_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    valid_date: Mapped[date] = mapped_column(Date, primary_key=True)
    precip_mm: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32))   # напр. era5_land


class Subscription(Base):
    """Подписка чата на изменения прогноза по локации (US-SUB-1)."""

    __tablename__ = "subscription"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    location_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

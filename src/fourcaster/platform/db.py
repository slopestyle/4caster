"""Фабрика подключения к Postgres (Supabase, ADR-0013).

Через Transaction pooler (pgbouncer) серверные prepared statements надо
отключать — иначе psycopg ломается в transaction-режиме пула.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from fourcaster.platform.config import database_url


def make_engine(url: str | None = None) -> Engine:
    return create_engine(
        url or database_url(),
        pool_pre_ping=True,
        # pgbouncer transaction mode: без server-side prepared statements
        connect_args={"prepare_threshold": None},
    )


SessionFactory = sessionmaker


def _check() -> int:
    from sqlalchemy import text

    from fourcaster.platform.config import safe_dsn

    url = database_url()
    print(f"Подключение к: {safe_dsn(url)}")
    engine = make_engine(url)
    with engine.connect() as conn:
        version = conn.execute(text("select version()")).scalar_one()
    print("OK:", str(version).split(" on ")[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(_check())

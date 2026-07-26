"""Alembic environment (PRD §11.3, задача 0.4).

URL и metadata подаются из приложения; секрет читается из окружения,
не из alembic.ini. Для Supabase pooler отключены prepared statements.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from fourcaster.platform.config import database_url_direct, safe_dsn
from fourcaster.platform.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_url = database_url_direct()
config.set_main_option("sqlalchemy.url", _url)


def run_migrations_offline() -> None:
    context.configure(
        url=_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    print(f"Alembic → {safe_dsn(_url)}")  # без пароля
    section = config.get_section(config.config_ini_section, {})
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"prepare_threshold": None},
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

"""Конфигурация через переменные окружения (12-factor, FR-DOC-5).

Локально читает .env (не коммитится); в CI значения приходят из GitHub
Secrets. Секреты никогда не логируются — для вывода есть `safe_dsn()`.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_PROJECT_ROOT / ".env")


def database_url() -> str:
    """DSN для рантайма (Supabase Transaction pooler, порт 6543)."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL не задан (см. .env.example)")
    # SQLAlchemy + psycopg3
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def database_url_direct() -> str:
    """DSN для миграций Alembic.

    Прямое подключение Supabase (db.<ref>.supabase.co:5432) — IPv6-only и
    часто недоступно из IPv4-сетей. Поэтому для миграций используем Session
    pooler: тот же pooler-хост, что и рантайм, но порт 5432. Выводим его из
    DATABASE_URL (6543 → 5432), если не задан явный pooler-DSN."""
    explicit = os.environ.get("DATABASE_URL_DIRECT")
    if explicit and "pooler.supabase.com" in explicit:
        return explicit.replace("postgresql://", "postgresql+psycopg://", 1)
    # деривация Session pooler из рабочего Transaction pooler DSN
    return database_url().replace(":6543/", ":5432/")


def telegram_token() -> str:
    t = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not t:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан (см. .env.example)")
    return t


def telegram_webhook_secret() -> str | None:
    """Секрет заголовка X-Telegram-Bot-Api-Secret-Token (FR-TG-1). Опционален."""
    return os.environ.get("TELEGRAM_WEBHOOK_SECRET") or None


def safe_dsn(url: str) -> str:
    """Строка подключения без пароля — безопасна для логов."""
    parts = urlsplit(url)
    user = parts.username or ""
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{user}:***@{host}{port}" if user else f"{host}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))

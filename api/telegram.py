"""Точка входа Vercel (файл api/telegram.py → маршрут /api/telegram).

Vercel обслуживает ASGI-приложение `app`. Пакет живёт в src/ (layout
проекта), поэтому добавляем его в путь импорта.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fourcaster.modules.telegram_ui.webapp import app  # noqa: E402

__all__ = ["app"]

"""Точка входа Vercel (файл api/index.py; все пути ведёт сюда rewrite).

Vercel обслуживает ASGI-приложение `app`. Пакет живёт в src/ (layout
проекта), поэтому добавляем его в путь импорта. Если импорт приложения
падает (не установлен пакет, не найден модуль и т.п.) — отдаём трейс
текстом, чтобы диагностировать деплой по URL (секретов в трейсе нет).
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from fourcaster.modules.telegram_ui.webapp import app  # noqa: F401
except Exception:  # noqa: BLE001 — диагностика bring-up на Vercel
    _tb = traceback.format_exc()

    async def app(scope, receive, send):  # type: ignore[no-redef]
        if scope["type"] != "http":
            return
        body = ("IMPORT ERROR\n\n" + _tb).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 500,
            "headers": [(b"content-type", b"text/plain; charset=utf-8")],
        })
        await send({"type": "http.response.body", "body": body})


__all__ = ["app"]

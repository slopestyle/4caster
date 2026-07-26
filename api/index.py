"""Точка входа Vercel (файл api/index.py; все пути ведёт сюда route).

Vercel (@vercel/python) ищет ПЕРЕМЕННУЮ `app` на верхнем уровне модуля,
поэтому итоговое `app = _make_app()` — верхнеуровневое присваивание.
Пакет живёт в src/; при неудаче импорта отдаём трейс текстом, чтобы
диагностировать деплой по URL (секретов в трейсе нет).
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _make_app():
    try:
        from fourcaster.modules.telegram_ui.webapp import app as real_app
        return real_app
    except Exception:  # noqa: BLE001 — диагностика bring-up на Vercel
        tb = traceback.format_exc()

        async def fallback(scope, receive, send):
            if scope["type"] != "http":
                return
            body = ("IMPORT ERROR\n\n" + tb).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [(b"content-type", b"text/plain; charset=utf-8")],
            })
            await send({"type": "http.response.body", "body": body})

        return fallback


app = _make_app()

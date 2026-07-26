"""FastAPI webhook-приложение для Telegram (ASGI, деплой на Vercel, ADR-0013).

aiogram по умолчанию поднимает свой aiohttp-сервер — на serverless он не
годится. Поэтому тонкая ASGI-обёртка: принимает POST от Telegram и отдаёт
апдейт диспетчеру. Компоненты (Bot, Dispatcher, движок) создаются один раз
на «тёплый» инстанс.
"""

from __future__ import annotations

from functools import lru_cache

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request
from sqlalchemy.engine import Engine

from fourcaster.modules.telegram_ui.bot import create_bot, create_dispatcher
from fourcaster.platform.config import telegram_token, telegram_webhook_secret
from fourcaster.platform.db import make_engine

app = FastAPI(title="4CASTER bot")


@lru_cache(maxsize=1)
def _components() -> tuple[Bot, Dispatcher, Engine]:
    engine = make_engine(nullpool=True)  # serverless: без пула соединений
    bot = create_bot(telegram_token())
    dp = create_dispatcher(engine)
    return bot, dp, engine


async def _health() -> dict:
    return {"ok": True, "service": "4caster-bot"}


async def _webhook(request: Request, secret_header: str | None) -> dict:
    secret = telegram_webhook_secret()
    if secret and secret_header != secret:
        raise HTTPException(status_code=403, detail="bad secret token")

    bot, dp, _ = _components()
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}


# Алиасы путей: Vercel может передать ASGI как исходный путь, так и "/".
@app.get("/api/telegram")
@app.get("/")
async def health() -> dict:
    return await _health()


@app.post("/api/telegram")
@app.post("/")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    return await _webhook(request, x_telegram_bot_api_secret_token)

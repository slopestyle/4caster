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
from fastapi.responses import HTMLResponse
from sqlalchemy.engine import Engine

from fourcaster.modules.locations import CATALOG, get_location
from fourcaster.modules.telegram_ui.bot import create_bot, create_dispatcher
from fourcaster.modules.telegram_ui.miniapp_page import HTML as MINIAPP_HTML
from fourcaster.platform.config import telegram_token, telegram_webhook_secret
from fourcaster.platform.db import make_engine
from fourcaster.platform.read_model import get_card_full, get_history, list_cards

app = FastAPI(title="4CASTER")


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


@app.get("/api/telegram")
async def health() -> dict:
    return await _health()


# ---- Telegram Mini App: страница + JSON API (read-модель) ----

@app.get("/", response_class=HTMLResponse)
@app.get("/app", response_class=HTMLResponse)
async def miniapp() -> str:
    return MINIAPP_HTML


@app.get("/api/locations")
async def api_locations() -> dict:
    _, _, engine = _components()
    cards = list_cards(engine)
    locations = []
    for loc in CATALOG.values():
        c = cards.get(loc.id)
        locations.append({
            "id": loc.id, "name": loc.name,
            "elevation_m": loc.elevation_m, "cluster": loc.cluster,
            "computed_at": c["computed_at"] if c else None,
            "today": c["today"] if c else None,
            "days": c["days"] if c else [],
            "days_total": c["days_total"] if c else 0,
            "n_models": c["n_models"] if c else 0,
        })
    return {"locations": locations}


@app.get("/api/forecast")
async def api_forecast(location: str) -> dict:
    _, _, engine = _components()
    try:
        loc = get_location(location)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown location")
    data = get_card_full(engine, location)
    if data is None:
        raise HTTPException(status_code=404, detail="no forecast yet")
    return {
        "location": {
            "id": loc.id, "name": loc.name,
            "elevation_m": loc.elevation_m, "cluster": loc.cluster,
        },
        **data,
    }


@app.get("/api/models")
async def api_models() -> dict:
    """Состав консенсуса и стартовые веса (§8.2) — для плашки «N моделей»."""
    from fourcaster.modules.consensus.models import MODELS

    return {
        "models": [
            {"id": m.id, "name": m.name, "center": m.center, "weight": m.weight}
            for m in MODELS
        ]
    }


@app.get("/api/hourly")
async def api_hourly(location: str) -> dict:
    from fourcaster.modules.consensus.calculator import compute_hourly
    from fourcaster.modules.consensus.models import MODELS
    from fourcaster.modules.ingestion.infrastructure.openmeteo.client import OpenMeteoProvider

    try:
        loc = get_location(location)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown location")
    provider = OpenMeteoProvider()
    series = provider.fetch_hourly(
        lat=loc.lat, lon=loc.lon, elevation_m=loc.elevation_m,
        model_ids=[m.openmeteo_id for m in MODELS],
    )
    data = compute_hourly(series)
    return {"location": {"id": loc.id, "name": loc.name}, **data}


@app.get("/api/history")
async def api_history(location: str) -> dict:
    _, _, engine = _components()
    try:
        loc = get_location(location)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown location")
    hist = get_history(engine, location)
    return {"location": {"id": loc.id, "name": loc.name}, **hist}


@app.post("/api/telegram")
@app.post("/")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    return await _webhook(request, x_telegram_bot_api_secret_token)

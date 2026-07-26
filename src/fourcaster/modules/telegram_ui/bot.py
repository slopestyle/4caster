"""aiogram 3: Bot + Dispatcher и тонкие обработчики (PRD §15, ADR-0012).

Обработчики только транспортные: берут BotReply из service и отправляют.
Движок БД прокидывается через workflow_data диспетчера.
"""

from __future__ import annotations

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.engine import Engine

from fourcaster.modules.telegram_ui import service
from fourcaster.modules.telegram_ui.keyboards import FORECAST_CB_PREFIX

router = Router()


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    r = service.start_reply()
    await message.answer(r.text, reply_markup=r.keyboard)


@router.message(Command("locations"))
async def on_locations(message: Message) -> None:
    r = service.locations_reply()
    await message.answer(r.text, reply_markup=r.keyboard)


@router.message(Command("forecast"))
async def on_forecast(message: Message, command: CommandObject, engine: Engine) -> None:
    location_id = (command.args or "").strip() or None
    r = service.forecast_reply(engine, location_id)
    await message.answer(r.text, reply_markup=r.keyboard)


@router.callback_query(F.data.startswith(FORECAST_CB_PREFIX))
async def on_forecast_button(callback: CallbackQuery, engine: Engine) -> None:
    location_id = (callback.data or "")[len(FORECAST_CB_PREFIX):]
    r = service.forecast_reply(engine, location_id)
    if isinstance(callback.message, Message):
        await callback.message.answer(r.text, reply_markup=r.keyboard)
    await callback.answer()


def create_bot(token: str) -> Bot:
    return Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def create_dispatcher(engine: Engine) -> Dispatcher:
    dp = Dispatcher()
    dp["engine"] = engine  # инъекция в обработчики по имени параметра
    dp.include_router(router)
    return dp

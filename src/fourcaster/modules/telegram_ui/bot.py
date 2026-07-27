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
from fourcaster.modules.telegram_ui.keyboards import (
    FORECAST_CB_PREFIX,
    HELP_CB,
    LIST_CB,
    SUB_CB_PREFIX,
    UNSUB_CB_PREFIX,
)

router = Router()


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    r = service.start_reply()
    await message.answer(r.text, reply_markup=r.keyboard)


@router.message(Command("help"))
async def on_help(message: Message) -> None:
    r = service.help_reply()
    await message.answer(r.text, reply_markup=r.keyboard)


@router.callback_query(F.data == LIST_CB)
async def on_locations_button(callback: CallbackQuery) -> None:
    r = service.locations_reply()
    if isinstance(callback.message, Message):
        await callback.message.answer(r.text, reply_markup=r.keyboard)
    await callback.answer()


@router.callback_query(F.data == HELP_CB)
async def on_help_button(callback: CallbackQuery) -> None:
    r = service.help_reply()
    if isinstance(callback.message, Message):
        await callback.message.answer(r.text, reply_markup=r.keyboard)
    await callback.answer()


@router.message(Command("locations"))
async def on_locations(message: Message) -> None:
    r = service.locations_reply()
    await message.answer(r.text, reply_markup=r.keyboard)


@router.message(Command("forecast"))
async def on_forecast(message: Message, command: CommandObject, engine: Engine) -> None:
    location_id = (command.args or "").strip() or None
    r = service.forecast_reply(engine, location_id, message.chat.id)
    await message.answer(r.text, reply_markup=r.keyboard)


@router.message(Command("my"))
async def on_my(message: Message, engine: Engine) -> None:
    r = service.my_reply(engine, message.chat.id)
    await message.answer(r.text, reply_markup=r.keyboard)


@router.callback_query(F.data.startswith(FORECAST_CB_PREFIX))
async def on_forecast_button(callback: CallbackQuery, engine: Engine) -> None:
    location_id = (callback.data or "")[len(FORECAST_CB_PREFIX):]
    if isinstance(callback.message, Message):
        r = service.forecast_reply(engine, location_id, callback.message.chat.id)
        await callback.message.answer(r.text, reply_markup=r.keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith(SUB_CB_PREFIX))
async def on_subscribe(callback: CallbackQuery, engine: Engine) -> None:
    location_id = (callback.data or "")[len(SUB_CB_PREFIX):]
    if isinstance(callback.message, Message):
        r = service.set_subscription_reply(
            engine, callback.message.chat.id, location_id, on=True)
        await callback.message.edit_reply_markup(reply_markup=r.keyboard)
    await callback.answer("Подписка включена")


@router.callback_query(F.data.startswith(UNSUB_CB_PREFIX))
async def on_unsubscribe(callback: CallbackQuery, engine: Engine) -> None:
    location_id = (callback.data or "")[len(UNSUB_CB_PREFIX):]
    if isinstance(callback.message, Message):
        r = service.set_subscription_reply(
            engine, callback.message.chat.id, location_id, on=False)
        await callback.message.edit_reply_markup(reply_markup=r.keyboard)
    await callback.answer("Подписка отключена")


def create_bot(token: str) -> Bot:
    return Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def create_dispatcher(engine: Engine) -> Dispatcher:
    dp = Dispatcher()
    dp["engine"] = engine  # инъекция в обработчики по имени параметра
    dp.include_router(router)
    return dp

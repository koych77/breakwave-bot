import os
import logging
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, FSInputFile, CallbackQuery, Message
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, delete
from app.database import async_session, init_db
from app.models import Subscriber, Event, Season
from app.excel_parser import import_excel_to_db
from app.config import BOT_TOKEN, ADMIN_IDS, DATA_DIR, WEBAPP_URL

logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)


_dynamic_admins = set()


def is_admin(user_id: int) -> bool:
    if ADMIN_IDS:
        return user_id in ADMIN_IDS
    return user_id in _dynamic_admins


def register_admin(user_id: int):
    if not ADMIN_IDS and not _dynamic_admins:
        _dynamic_admins.add(user_id)
        logger.info(f"Auto-registered admin: {user_id}")


# --- FSM States ---

class EventForm(StatesGroup):
    name = State()
    event_type = State()
    emoji = State()
    date = State()
    time = State()
    location = State()
    description = State()
    fee = State()
    contact = State()
    photo = State()
    confirm = State()


class NotifyForm(StatesGroup):
    message = State()


# --- User commands ---

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    async with async_session() as s:
        existing = await s.execute(
            select(Subscriber).where(Subscriber.telegram_id == message.from_user.id)
        )
        sub = existing.scalar_one_or_none()
        if not sub:
            sub = Subscriber(
                telegram_id=message.from_user.id,
                first_name=message.from_user.first_name,
                username=message.from_user.username,
                is_active=True,
            )
            s.add(sub)
        else:
            sub.is_active = True
            sub.first_name = message.from_user.first_name
            sub.username = message.from_user.username
        await s.commit()

    # Auto-register first user as admin
    register_admin(message.from_user.id)

    webapp_url = WEBAPP_URL or "https://web-production-7b91a.up.railway.app"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🏆 Открыть рейтинг",
            web_app=WebAppInfo(url=f"{webapp_url}/webapp/")
        )],
        [InlineKeyboardButton(
            text="📅 Мероприятия",
            web_app=WebAppInfo(url=f"{webapp_url}/webapp/#events")
        )],
    ])

    await message.answer(
        "👋 Добро пожаловать в <b>Break Wave Ranking</b>!\n\n"
        "🏆 Здесь ты можешь следить за рейтингом участников, "
        "результатами мероприятий и предстоящими соревнованиями.\n\n"
        "Нажми кнопку ниже, чтобы открыть приложение:",
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "📋 <b>Команды:</b>\n\n"
        "/start — Открыть приложение\n"
        "/help — Список команд\n"
    )
    if is_admin(message.from_user.id):
        text += (
            "\n<b>👑 Админ-команды:</b>\n"
            "📎 Отправить .xlsx файл — обновить рейтинг\n"
            "/event_add — добавить мероприятие\n"
            "/event_list — список мероприятий\n"
            "/event_delete — удалить мероприятие\n"
            "/notify — уведомление всем\n"
            "/stats — статистика подписчиков\n"
            "/season_new — новый сезон\n"
        )
    await message.answer(text, parse_mode="HTML")


# --- Admin: Excel upload ---

@router.message(F.document)
async def handle_document(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return

    doc = message.document
    if not doc.file_name.endswith((".xlsx", ".xls")):
        await message.answer("❌ Отправь файл в формате .xlsx")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, обновить", callback_data="excel_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="excel_cancel"),
        ]
    ])
    # Save file temporarily
    file = await bot.get_file(doc.file_id)
    file_path = DATA_DIR / "upload.xlsx"
    await bot.download_file(file.file_path, str(file_path))

    await message.answer(
        f"📄 Файл <b>{doc.file_name}</b> получен.\n\nОбновить данные рейтинга?",
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(F.data == "excel_confirm")
async def excel_confirm(callback: CallbackQuery):
    await callback.message.edit_text("⏳ Обновляю данные...")

    file_path = DATA_DIR / "upload.xlsx"
    try:
        async with async_session() as s:
            result = await import_excel_to_db(s, str(file_path))

        events_str = ", ".join(result["updated_events"]) if result["updated_events"] else "нет новых"
        await callback.message.edit_text(
            f"✅ <b>Данные обновлены!</b>\n\n"
            f"👥 Участников: {result['participants']}\n"
            f"📅 Обновлённые мероприятия: {events_str}\n\n"
            f"Отправить уведомление подписчикам?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📢 Да, уведомить", callback_data="notify_update"),
                    InlineKeyboardButton(text="⏭ Пропустить", callback_data="notify_skip"),
                ]
            ]),
        )
    except Exception as e:
        logger.error(f"Excel import error: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {e}")


@router.callback_query(F.data == "excel_cancel")
async def excel_cancel(callback: CallbackQuery):
    await callback.message.edit_text("❌ Отменено.")


@router.callback_query(F.data == "notify_update")
async def notify_update(callback: CallbackQuery):
    await callback.message.edit_text("📢 Отправляю уведомления...")
    webapp_url = WEBAPP_URL or "https://web-production-7b91a.up.railway.app"

    count = await send_notification_to_all(
        "🏆 <b>Рейтинг обновлён!</b>\n\n"
        "Новые результаты уже доступны. Открой приложение, чтобы посмотреть!",
        webapp_url
    )
    await callback.message.edit_text(f"✅ Уведомление отправлено {count} подписчикам!")


@router.callback_query(F.data == "notify_skip")
async def notify_skip(callback: CallbackQuery):
    await callback.message.edit_text("✅ Готово! Уведомление пропущено.")


# --- Admin: Add Event ---

@router.message(Command("event_add"))
async def cmd_event_add(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Break Wave (школа)", callback_data="etype_school")],
        [InlineKeyboardButton(text="🌍 Другое соревнование", callback_data="etype_external")],
    ])
    await message.answer("Какой тип мероприятия?", reply_markup=kb)
    await state.set_state(EventForm.event_type)


@router.callback_query(F.data.startswith("etype_"), EventForm.event_type)
async def event_type_chosen(callback: CallbackQuery, state: FSMContext):
    etype = "school" if "school" in callback.data else "external"
    await state.update_data(event_type=etype)
    await callback.message.edit_text("📝 Введи название мероприятия:")
    await state.set_state(EventForm.name)


@router.message(EventForm.name)
async def event_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📅 Дата (например: 20 апреля 2026):")
    await state.set_state(EventForm.date)


@router.message(EventForm.date)
async def event_date(message: types.Message, state: FSMContext):
    await state.update_data(date=message.text)
    await message.answer("🕐 Время начала (например: 12:00) или напиши 'нет':")
    await state.set_state(EventForm.time)


@router.message(EventForm.time)
async def event_time(message: types.Message, state: FSMContext):
    val = message.text if message.text.lower() != "нет" else None
    await state.update_data(time=val)
    await message.answer("📍 Место проведения:")
    await state.set_state(EventForm.location)


@router.message(EventForm.location)
async def event_location(message: types.Message, state: FSMContext):
    await state.update_data(location=message.text)
    await message.answer("📋 Описание (или 'нет'):")
    await state.set_state(EventForm.description)


@router.message(EventForm.description)
async def event_description(message: types.Message, state: FSMContext):
    val = message.text if message.text.lower() != "нет" else None
    await state.update_data(description=val)
    await message.answer("💰 Взнос за участие (или 'нет'):")
    await state.set_state(EventForm.fee)


@router.message(EventForm.fee)
async def event_fee(message: types.Message, state: FSMContext):
    val = message.text if message.text.lower() != "нет" else None
    await state.update_data(fee=val)
    await message.answer("📱 Контакт для регистрации (или 'нет'):")
    await state.set_state(EventForm.contact)


@router.message(EventForm.contact)
async def event_contact(message: types.Message, state: FSMContext):
    val = message.text if message.text.lower() != "нет" else None
    await state.update_data(contact=val)
    await message.answer("🖼 Отправь фото/постер мероприятия (или напиши 'нет'):")
    await state.set_state(EventForm.photo)


@router.message(EventForm.photo, F.photo)
async def event_photo_file(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    photo_path = DATA_DIR / f"event_{photo.file_id}.jpg"
    await bot.download_file(file.file_path, str(photo_path))
    await state.update_data(photo_path=str(photo_path))
    await _confirm_event(message, state)


@router.message(EventForm.photo)
async def event_photo_skip(message: types.Message, state: FSMContext):
    await state.update_data(photo_path=None)
    await _confirm_event(message, state)


async def _confirm_event(message: types.Message, state: FSMContext):
    data = await state.get_data()
    etype_label = "🏠 Break Wave" if data["event_type"] == "school" else "🌍 Другое"

    text = (
        f"<b>Подтверди мероприятие:</b>\n\n"
        f"📝 {data['name']}\n"
        f"📂 {etype_label}\n"
        f"📅 {data['date']}\n"
    )
    if data.get("time"):
        text += f"🕐 {data['time']}\n"
    text += f"📍 {data['location']}\n"
    if data.get("description"):
        text += f"📋 {data['description']}\n"
    if data.get("fee"):
        text += f"💰 {data['fee']}\n"
    if data.get("contact"):
        text += f"📱 {data['contact']}\n"
    text += f"🖼 Фото: {'да' if data.get('photo_path') else 'нет'}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Сохранить", callback_data="event_save"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="event_cancel"),
        ]
    ])
    await message.answer(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(EventForm.confirm)


@router.callback_query(F.data == "event_save", EventForm.confirm)
async def event_save(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    async with async_session() as s:
        # Get current season
        res = await s.execute(select(Season).where(Season.is_current == True))
        season = res.scalar_one_or_none()
        season_id = season.id if season else None

        event = Event(
            name=data["name"],
            emoji="🏆",
            event_type=data["event_type"],
            season_id=season_id,
            date=data["date"],
            time=data.get("time"),
            location=data["location"],
            description=data.get("description"),
            fee=data.get("fee"),
            contact=data.get("contact"),
            photo_path=data.get("photo_path"),
            status="upcoming",
            multiplier=1,
            sort_order=100,
        )
        s.add(event)
        await s.commit()

    await callback.message.edit_text("✅ Мероприятие добавлено!")

    webapp_url = WEBAPP_URL or "https://web-production-7b91a.up.railway.app"
    count = await send_notification_to_all(
        f"📅 <b>Новое мероприятие!</b>\n\n"
        f"🏆 {data['name']}\n"
        f"📅 {data['date']}\n"
        f"📍 {data['location']}",
        webapp_url
    )
    await callback.message.answer(f"📢 Уведомление отправлено {count} подписчикам!")
    await state.clear()


@router.callback_query(F.data == "event_cancel", EventForm.confirm)
async def event_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ Отменено.")
    await state.clear()


# --- Admin: List events ---

@router.message(Command("event_list"))
async def cmd_event_list(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    async with async_session() as s:
        result = await s.execute(select(Event).order_by(Event.sort_order, Event.created_at))
        events = result.scalars().all()

    if not events:
        await message.answer("Нет мероприятий.")
        return

    text = "<b>📅 Мероприятия:</b>\n\n"
    for e in events:
        etype = "🏠" if e.event_type == "school" else "🌍"
        text += f"{etype} <b>{e.name}</b> (ID: {e.id})\n"
        if e.date:
            text += f"   📅 {e.date}\n"
        text += f"   Статус: {e.status}\n\n"

    await message.answer(text, parse_mode="HTML")


# --- Admin: Delete event ---

@router.message(Command("event_delete"))
async def cmd_event_delete(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    async with async_session() as s:
        result = await s.execute(
            select(Event).where(Event.event_type.in_(["school", "external"])).order_by(Event.created_at)
        )
        events = result.scalars().all()

    if not events:
        await message.answer("Нет мероприятий для удаления.")
        return

    buttons = []
    for e in events:
        etype = "🏠" if e.event_type == "school" else "🌍"
        buttons.append([InlineKeyboardButton(
            text=f"{etype} {e.name} ({e.date or 'без даты'})",
            callback_data=f"edel_{e.id}"
        )])

    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="edel_cancel")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выбери мероприятие для удаления:", reply_markup=kb)


@router.callback_query(F.data.startswith("edel_"))
async def event_delete_confirm(callback: CallbackQuery):
    if callback.data == "edel_cancel":
        await callback.message.edit_text("❌ Отменено.")
        return

    event_id = int(callback.data.replace("edel_", ""))
    async with async_session() as s:
        await s.execute(delete(Result).where(Result.event_id == event_id))
        await s.execute(delete(Event).where(Event.id == event_id))
        await s.commit()

    await callback.message.edit_text("✅ Мероприятие удалено!")


# --- Admin: Notify ---

@router.message(Command("notify"))
async def cmd_notify(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer("📢 Введи текст уведомления:")
    await state.set_state(NotifyForm.message)


@router.message(NotifyForm.message)
async def notify_send(message: types.Message, state: FSMContext):
    webapp_url = WEBAPP_URL or "https://web-production-7b91a.up.railway.app"
    count = await send_notification_to_all(message.text, webapp_url)
    await message.answer(f"✅ Уведомление отправлено {count} подписчикам!")
    await state.clear()


# --- Admin: Stats ---

@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    async with async_session() as s:
        total = await s.execute(select(Subscriber))
        subs = total.scalars().all()
        active = sum(1 for sub in subs if sub.is_active)

    await message.answer(
        f"📊 <b>Статистика бота:</b>\n\n"
        f"👥 Всего подписчиков: {len(subs)}\n"
        f"✅ Активных: {active}",
        parse_mode="HTML",
    )


# --- Admin: New Season ---

@router.message(Command("season_new"))
async def cmd_season_new(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, новый сезон", callback_data="season_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="season_cancel"),
        ]
    ])
    await message.answer(
        "⚠️ Начать новый сезон?\n\nТекущий сезон будет архивирован. "
        "Все данные сохранятся в истории.",
        reply_markup=kb,
    )


@router.callback_query(F.data == "season_confirm")
async def season_confirm(callback: CallbackQuery):
    async with async_session() as s:
        await s.execute(
            Season.__table__.update().where(Season.is_current == True).values(is_current=False)
        )
        new_season = Season(name="Новый сезон", is_current=True)
        s.add(new_season)
        await s.commit()

    await callback.message.edit_text("✅ Новый сезон создан! Загрузи Excel с данными.")


@router.callback_query(F.data == "season_cancel")
async def season_cancel(callback: CallbackQuery):
    await callback.message.edit_text("❌ Отменено.")


# --- Notification helper ---

async def send_notification_to_all(text: str, webapp_url: str) -> int:
    async with async_session() as s:
        result = await s.execute(select(Subscriber).where(Subscriber.is_active == True))
        subscribers = result.scalars().all()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🏆 Открыть",
            web_app=WebAppInfo(url=f"{webapp_url}/webapp/")
        )],
    ])

    count = 0
    for sub in subscribers:
        try:
            await bot.send_message(sub.telegram_id, text, parse_mode="HTML", reply_markup=kb)
            count += 1
        except Exception as e:
            logger.warning(f"Failed to send to {sub.telegram_id}: {e}")
            async with async_session() as s:
                existing = await s.execute(
                    select(Subscriber).where(Subscriber.telegram_id == sub.telegram_id)
                )
                subscriber = existing.scalar_one_or_none()
                if subscriber:
                    subscriber.is_active = False
                    await s.commit()
    return count

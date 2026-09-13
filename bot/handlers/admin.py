import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.config import config
from bot.database.db import get_all_users, get_global_stats

router = Router()
logger = logging.getLogger(__name__)


class BroadcastState(StatesGroup):
    waiting_for_text = State()


def _is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


# ─── Команда /admin ───

@router.message(Command("admin"))
async def cmd_admin(msg: Message, state: FSMContext):
    if not _is_admin(msg.from_user.id):
        await msg.answer("⛔ У тебя нет доступа к админ-панели.")
        return
    await state.clear()
    await msg.answer(
        "🔧 <b>Админ-панель</b>\n\nВыбери действие:",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )


def admin_menu_kb():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"),
        ],
        [
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"),
            InlineKeyboardButton(text="🔄 Статус бота", callback_data="admin_status"),
        ],
    ])


# ─── Статистика ───

@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("⛔ Нет доступа", show_alert=True)
        return

    stats = await get_global_stats()

    text = "📊 <b>Статистика бота</b>\n\n"
    text += f"👤 Пользователей: {stats['total_users']}\n"
    text += f"📝 Всего сессий: {stats['total_sessions']}\n"
    text += f"✅ Завершённых: {stats['completed_sessions']}\n"
    text += f"📈 Средний балл: {stats['avg_score']}\n"
    text += f"💬 Ответов на задания: {stats['total_answers']}\n\n"

    if stats.get("by_scenario"):
        text += "<b>По сценариям:</b>\n"
        for scenario, data in stats["by_scenario"].items():
            name = {
                "university": "🎓 Выбор вуза",
                "job": "💼 Поиск работы",
                "adaptation": "🤝 Адаптация",
            }.get(scenario, scenario)
            text += f"  {name}: {data['sessions']} сессий, средний {data['avg_score']}\n"

    await cb.message.edit_text(text, reply_markup=admin_menu_kb(), parse_mode="HTML")
    await cb.answer()


# ─── Пользователи ───

@router.callback_query(F.data == "admin_users")
async def cb_admin_users(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("⛔ Нет доступа", show_alert=True)
        return

    users = await get_all_users(limit=10)

    text = "👥 <b>Последние пользователи</b>\n\n"
    for u in users:
        name = u.get("first_name") or u.get("username") or str(u["user_id"])
        # Экранируем HTML-символы чтобы не сломать parse_mode
        name = str(name).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text += f"• {name} (id: {u['user_id']}) — {u.get('current_scenario', '?')}\n"

    if not users:
        text += "Пока нет пользователей."

    await cb.message.edit_text(text, reply_markup=admin_menu_kb(), parse_mode="HTML")
    await cb.answer()


# ─── Рассылка ───

@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb.from_user.id):
        await cb.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.set_state(BroadcastState.waiting_for_text)
    await cb.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "Отправь мне текст сообщения, и я разошлю его всем пользователям.\n"
        "Для отмены нажми «❌ Отмена».",
        reply_markup=broadcast_cancel_kb(),
        parse_mode="HTML",
    )
    await cb.answer()


def broadcast_cancel_kb():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcast_cancel")]
    ])


@router.callback_query(F.data == "admin_broadcast_cancel")
async def cb_broadcast_cancel(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb.from_user.id):
        await cb.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.clear()
    await cb.message.edit_text(
        "🔧 <b>Админ-панель</b>\n\nВыбери действие:",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(BroadcastState.waiting_for_text, F.text)
async def handle_broadcast_text(msg: Message, state: FSMContext):
    if not _is_admin(msg.from_user.id):
        await state.clear()
        return

    await state.clear()

    users = await get_all_users(limit=9999)
    sent = 0
    failed = 0

    import asyncio
    from aiogram.exceptions import TelegramRetryAfter

    for user in users:
        try:
            # Ограничиваем длину сообщения (Telegram лимит — 4096 символов)
            text_to_send = msg.text[:4096] if msg.text else ""
            await msg.bot.send_message(user["user_id"], text_to_send)
            sent += 1
            await asyncio.sleep(0.1)
        except TelegramRetryAfter as e:
            logger.warning(f"Flood control, жду {e.retry_after} сек")
            await asyncio.sleep(e.retry_after)
            # Повторная попытка после ожидания
            try:
                await msg.bot.send_message(user["user_id"], msg.text)
                sent += 1
            except Exception:
                failed += 1
        except Exception as e:
            logger.warning(f"Не удалось отправить пользователю {user['user_id']}: {e}")
            failed += 1

    await msg.answer(
        f"✅ Рассылка завершена!\n"
        f"Отправлено: {sent}\n"
        f"Не доставлено: {failed}",
        reply_markup=admin_menu_kb(),
    )


# ─── Статус бота ───

@router.callback_query(F.data == "admin_status")
async def cb_admin_status(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("⛔ Нет доступа", show_alert=True)
        return

    text = (
        "🔄 <b>Статус бота</b>\n\n"
        f"🤖 Имя: AI-наставник\n"
        f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"🔧 AI: GigaChat ({config.GIGACHAT_MODEL})\n"
        f"👥 Админов: {len(config.ADMIN_IDS)}"
    )

    await cb.message.edit_text(text, reply_markup=admin_menu_kb(), parse_mode="HTML")
    await cb.answer()


# ─── Назад в меню ───

@router.callback_query(F.data == "admin_menu")
async def cb_admin_menu(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb.from_user.id):
        await cb.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.clear()
    await cb.message.edit_text(
        "🔧 <b>Админ-панель</b>\n\nВыбери действие:",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )
    await cb.answer()

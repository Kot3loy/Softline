"""Хендлер информационного режима — диалог с AI по выбранному сценарию."""

import os
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.utils.keyboards import back_to_menu_kb
from bot.utils.voice import text_to_speech
from bot.core.scenarios import answer_info_question, get_welcome_message
from bot.core.ai_engine import _sanitize_input
from bot.database.db import update_user, get_or_create_user

logger = logging.getLogger(__name__)

router = Router()

DISCLAIMER = (
    "\n\n⚠️ Рекомендации носят информационный характер и не заменяют "
    "официальные требования вузов и работодателей."
)

# маркеры ошибок — если ответ начинается с них, дисклеймер не показываем
_ERROR_MARKERS = (
    "Извини", "Не удалось", "Слишком много", "ошибка",
    "Ошибка", "не могу", "Попробуй позже",
)


def _should_show_disclaimer(answer: str) -> bool:
    """Показывать дисклеймер только при полезном ответе AI"""
    if not answer or len(answer) < 80:
        return False
    for marker in _ERROR_MARKERS:
        if answer.startswith(marker):
            return False
    return True


class InfoState(StatesGroup):
    """Состояние информационного режима"""
    in_chat = State()


@router.callback_query(F.data.startswith("info_"))
async def cb_info_mode(cb: CallbackQuery, state: FSMContext):
    """Информационный режим — начало диалога"""
    scenario = cb.data.removeprefix("info_")
    await state.set_state(InfoState.in_chat)
    await state.update_data(scenario=scenario)

    await update_user(cb.from_user.id, current_scenario=scenario)

    welcome = await get_welcome_message(scenario)

    await cb.message.edit_text(
        f"📚 <b>Информационный режим</b>\n\n{welcome}",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML",
    )
    await cb.answer()


KNOWN_BUTTONS = {
    "🎓 Выбор вуза", "💼 Поиск работы", "🤝 Адаптация в компании",
    "📊 Мой прогресс", "ℹ️ Дисклеймер", "🔊 Включить голос", "🔇 Выключить голос",
}


@router.message(InfoState.in_chat, F.text & ~F.text.startswith("/") & ~F.text.in_(KNOWN_BUTTONS))
async def handle_text_message(msg: Message, state: FSMContext):
    """Обработка текстовых сообщений — ответ через AI"""
    data = await state.get_data()
    scenario = data.get("scenario", "university")
    user_id = msg.from_user.id

    await msg.bot.send_chat_action(msg.chat.id, "typing")

    clean_text = _sanitize_input(msg.text)
    answer = await answer_info_question(clean_text, scenario, user_id=user_id)

    # Дисклеймер только при полезном ответе
    suffix = DISCLAIMER if _should_show_disclaimer(answer) else ""

    # Проверяем включён ли голос — если да, отправляем голосом + текст
    user_data = await get_or_create_user(user_id)
    voice_enabled = user_data.get("voice_enabled", 0) == 1

    if voice_enabled:
        voice_file = await text_to_speech(answer)
        try:
            if voice_file:
                await msg.answer_voice(FSInputFile(voice_file))
                await msg.answer(f"📝 <b>Текст:</b>\n{answer}{suffix}", parse_mode="HTML")
                return
        finally:
            if voice_file and os.path.exists(voice_file):
                os.remove(voice_file)

    await msg.answer(f"{answer}{suffix}", parse_mode="HTML")

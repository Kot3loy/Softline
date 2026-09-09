"""Хендлер информационного режима — диалог с AI по выбранному сценарию."""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.utils.keyboards import back_to_menu_kb
from bot.utils.voice import text_to_speech
from bot.core.scenarios import answer_info_question, get_welcome_message
from bot.database.db import update_user, get_or_create_user

router = Router()

DISCLAIMER = (
    "⚠️ Рекомендации носят информационный характер и не заменяют "
    "официальные требования вузов и работодателей."
)


class InfoState(StatesGroup):
    """Состояние информационного режима"""
    in_chat = State()


@router.callback_query(F.data.startswith("info_"))
async def cb_info_mode(cb: CallbackQuery, state: FSMContext):
    """Информационный режим — начало диалога"""
    scenario = cb.data.replace("info_", "")
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

    answer = await answer_info_question(msg.text, scenario, user_id=user_id)

    # Проверяем включён ли голос — если да, отправляем голосом + текст
    user_data = await get_or_create_user(user_id)
    voice_enabled = user_data.get("voice_enabled", 0) == 1

    if voice_enabled:
        voice_file = await text_to_speech(answer)
        if voice_file:
            await msg.answer_voice(FSInputFile(voice_file))
            await msg.answer(f"📝 <b>Текст:</b>\n{answer}\n\n{DISCLAIMER}", parse_mode="HTML")
            import os
            os.remove(voice_file)
            return

    await msg.answer(f"{answer}\n\n{DISCLAIMER}", parse_mode="HTML")

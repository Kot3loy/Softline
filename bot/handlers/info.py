# информационный режим — юзер болтает с ботом, бот отвечает через ai по базе знаний

import os
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.translations import t
from bot.utils.keyboards import back_to_menu_kb
from bot.utils.lang import KNOWN_BUTTONS
from bot.utils.voice import text_to_speech
from bot.core.scenarios import answer_info_question, get_welcome_message
from bot.core.ai_engine import _sanitize_input, _ERROR_MARKERS
from bot.database.db import update_user, get_or_create_user
from bot.handlers.start import _replace_card, _remember

logger = logging.getLogger(__name__)

router = Router()


def _should_show_disclaimer(answer: str) -> bool:
    # дисклеймер только когда ответ реально содержательный,
    # а не "извини, ai перегружен"
    if not answer or len(answer) < 80:
        return False
    for marker in _ERROR_MARKERS:
        if answer.startswith(marker):
            return False
    return True


class InfoState(StatesGroup):
    in_chat = State()


@router.callback_query(F.data.startswith("info_") & ~F.data.startswith("info_from_inline_"))
async def cb_info_mode(cb: CallbackQuery, state: FSMContext):
    # кнопка "информационный режим" — приветствие по сценарию
    scenario = cb.data.removeprefix("info_")
    await state.set_state(InfoState.in_chat)
    await state.update_data(scenario=scenario)

    await update_user(cb.from_user.id, current_scenario=scenario)

    user_data = await get_or_create_user(cb.from_user.id)
    lang = user_data.get("language", "ru")

    welcome = await get_welcome_message(scenario, lang)

    # сессия инфо-режима: приветствие только на первом входе
    from bot.core.ai_engine import has_history
    if not has_history(cb.from_user.id):
        await _replace_card(
            cb.message,
            f"{t('info_header', lang)}\n\n{welcome}",
            kb=back_to_menu_kb(lang),
        )
    else:
        await _replace_card(
            cb.message,
            t("info_continue", lang),
            kb=back_to_menu_kb(lang),
        )
    await cb.answer()


@router.message(InfoState.in_chat, F.text & ~F.text.startswith("/") & ~F.text.in_(KNOWN_BUTTONS))
async def handle_text_message(msg: Message, state: FSMContext):
    # любой текст в режиме инфо — вопрос к ai
    data = await state.get_data()
    scenario = data.get("scenario", "university")
    user_id = msg.from_user.id

    await msg.bot.send_chat_action(msg.chat.id, "typing")

    user_data = await get_or_create_user(user_id)
    lang = user_data.get("language", "ru")

    clean_text = _sanitize_input(msg.text)

    # Если язык не русский — переводим вопрос в русский для AI
    if lang != "ru":
        from bot.utils.translator import translate_text
        clean_text = await translate_text(clean_text, target_lang="ru")

    answer = await answer_info_question(clean_text, scenario, user_id=user_id, lang=lang)

    # Переводим ответ на язык пользователя
    if lang != "ru":
        from bot.utils.translator import translate_text
        answer = await translate_text(answer, target_lang=lang)

    # Дисклеймер только при полезном ответе
    disclaimer = t("disclaimer", lang) if _should_show_disclaimer(answer) else ""

    # Проверяем включён ли голос — если да, отправляем голосом + текст
    voice_enabled = user_data.get("voice_enabled", 0) == 1

    if voice_enabled:
        voice_file = await text_to_speech(answer)
        try:
            if voice_file:
                await msg.answer_voice(FSInputFile(voice_file))
                sent = await msg.answer(
                    f"{t('voice_text_prefix', lang, text=answer)}{disclaimer}",
                    parse_mode="HTML",
                )
                try:
                    _remember(msg.chat.id, getattr(sent, "message_id", None))
                except Exception:
                    pass
                return
        finally:
            if voice_file and os.path.exists(voice_file):
                os.remove(voice_file)

    sent = await msg.answer(f"{answer}{disclaimer}", parse_mode="HTML")
    try:
        _remember(msg.chat.id, getattr(sent, "message_id", None))
    except Exception:
        pass

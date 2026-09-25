"""Хендлеры старта — приветствие, главное меню, настройки, команды."""

import logging
import asyncio
import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart, Command, StateFilter

from bot.translations import t
from bot.utils.keyboards import main_menu_kb, scenario_info_kb, settings_kb, progress_kb
from bot.utils.lang import get_lang, KNOWN_BUTTONS
from bot.utils.voice import text_to_speech
from bot.core.ai_engine import _sanitize_input
from bot.database.db import get_or_create_user, get_user_stats, update_user

logger = logging.getLogger(__name__)

router = Router()

# Запоминаем id последнего сообщения бота для edit вместо новых сообщений
_last_msg: dict[int, int] = {}

STALE_LIMIT = 6


def _remember(chat_id: int, message_id: int):
    if isinstance(message_id, int) and message_id:
        _last_msg[chat_id] = message_id


def _about_text(lang: str, include_disclaimer: bool = False) -> str:
    """Собрать текст раздела «О боте»"""
    parts = [
        t("about_header", lang),
        t("about_desc", lang),
        t("about_features", lang),
        t("about_f1", lang), t("about_f2", lang), t("about_f3", lang),
        t("about_f4", lang), t("about_f5", lang), t("about_f6", lang),
        t("about_howto", lang),
        t("about_h1", lang), t("about_h2", lang), t("about_h3", lang), t("about_h4", lang),
        t("about_settings", lang),
        t("about_progress", lang),
        t("about_export", lang),
        t("about_credits", lang),
        t("about_tech", lang),
    ]
    if include_disclaimer:
        parts.append(t("about_disclaimer", lang))
    return "\n\n".join(parts)


async def _show_screen(msg: Message, text: str, kb=None, parse_mode: str = "HTML"):
    """Показать экран: edit последнего сообщения бота, иначе новое"""
    chat_id = msg.chat.id
    mid = _last_msg.get(chat_id)
    msg_id = getattr(msg, "message_id", 0) or 0
    if mid and msg_id - mid <= STALE_LIMIT:
        try:
            await msg.bot.edit_message_text(
                text, chat_id=chat_id, message_id=mid,
                reply_markup=kb, parse_mode=parse_mode,
            )
            return
        except Exception:
            pass  # сообщение удалено/не изменилось — шлём новое
    sent = await msg.answer(text, reply_markup=kb, parse_mode=parse_mode)
    _remember(chat_id, getattr(sent, "message_id", None))


@router.message(CommandStart())
async def cmd_start(msg: Message):
    """Приветствие"""
    user_data = await get_or_create_user(
        user_id=msg.from_user.id,
        username=msg.from_user.username,
        first_name=msg.from_user.first_name,
        last_name=msg.from_user.last_name,
    )
    lang = get_lang(user_data)
    sent = await msg.answer(t("welcome_msg", lang), reply_markup=main_menu_kb(lang), parse_mode="HTML")
    _remember(msg.chat.id, getattr(sent, "message_id", None))


@router.message(Command("help"))
@router.message(Command("disclaimer"))
async def cmd_help(msg: Message):
    """Справка и дисклеймер"""
    user_data = await get_or_create_user(msg.from_user.id)
    lang = get_lang(user_data)
    about = _about_text(lang, include_disclaimer=True)
    await msg.answer(about, parse_mode="HTML")


def _settings_text(lang: str) -> str:
    """Текст экрана настроек — заголовок + подсказка про голос"""
    return t("settings_header", lang) + "\n\n" + t("settings_voice_hint", lang)


@router.message(F.text.in_({t("btn_settings", "ru"), t("btn_settings", "en")}))
async def btn_settings(msg: Message):
    """Меню настроек"""
    user_data = await get_or_create_user(msg.from_user.id)
    lang = get_lang(user_data)
    voice_enabled = user_data.get("voice_enabled", 0) == 1
    await _show_screen(
        msg,
        _settings_text(lang),
        kb=settings_kb(voice_enabled, lang),
    )


@router.callback_query(F.data == "settings_voice")
async def cb_settings_voice(cb: CallbackQuery):
    """Переключение голоса"""
    user_data = await get_or_create_user(cb.from_user.id)
    lang = get_lang(user_data)
    new_value = 0 if user_data.get("voice_enabled", 0) == 1 else 1
    await update_user(cb.from_user.id, voice_enabled=new_value)

    voice_enabled = new_value == 1
    await cb.message.edit_reply_markup(reply_markup=settings_kb(voice_enabled, lang))
    status_msg = t("voice_enabled", lang) if voice_enabled else t("voice_disabled", lang)
    await cb.answer(status_msg, show_alert=True)


@router.callback_query(F.data.in_({"set_lang_ru", "set_lang_en"}))
async def cb_set_language(cb: CallbackQuery):
    """Переключение языка по конкретной кнопке"""
    user_data = await get_or_create_user(cb.from_user.id)
    new_lang = "ru" if cb.data == "set_lang_ru" else "en"
    await update_user(cb.from_user.id, language=new_lang)

    voice_enabled = user_data.get("voice_enabled", 0) == 1
    await cb.message.edit_text(
        _settings_text(new_lang),
        reply_markup=settings_kb(voice_enabled, new_lang),
        parse_mode="HTML",
    )
    await cb.answer(f"Language → {new_lang.upper()}", show_alert=True)


_reset_confirm_users = set()


@router.callback_query(F.data == "progress_reset")
async def cb_progress_reset(cb: CallbackQuery):
    """Сброс прогресса"""
    user_id = cb.from_user.id
    user_data = await get_or_create_user(user_id)
    lang = get_lang(user_data)

    if user_id in _reset_confirm_users:
        _reset_confirm_users.discard(user_id)
        from bot.database.db import reset_progress
        await reset_progress(user_id)
        from bot.handlers.examiner import exam_sessions
        exam_sessions.pop(user_id, None)
        await cb.answer(t("reset_done", lang), show_alert=True)
        await cb.message.edit_reply_markup(reply_markup=progress_kb(lang))
    else:
        _reset_confirm_users.add(user_id)
        await cb.answer(t("reset_confirm", lang), show_alert=True)
        async def _clear_confirm():
            await asyncio.sleep(30)
            _reset_confirm_users.discard(user_id)
        asyncio.create_task(_clear_confirm())


@router.callback_query(F.data == "settings_about")
async def cb_settings_about(cb: CallbackQuery):
    """О боте"""
    user_data = await get_or_create_user(cb.from_user.id)
    lang = get_lang(user_data)
    await cb.message.edit_text(_about_text(lang), reply_markup=None, parse_mode="HTML")
    await cb.answer()


@router.message(Command("export"))
async def cmd_export(msg: Message):
    """Команда /export — генерация PDF-отчёта"""
    from bot.handlers.pdf_export import generate_report_outcomes

    user_data = await get_or_create_user(msg.from_user.id)
    lang = get_lang(user_data)
    stats = await get_user_stats(msg.from_user.id)

    if not stats.get("scenarios"):
        await msg.answer(t("pdf_no_results", lang))
        return

    await msg.answer(t("pdf_generating", lang))

    success_count = 0
    for scenario, path in await generate_report_outcomes(msg.from_user.id, stats["scenarios"]):
        if path is None:
            await msg.answer(t("pdf_error", lang, scenario=scenario))
            continue
        await msg.answer_document(
            FSInputFile(path),
            caption=t("pdf_caption", lang, scenario=scenario),
        )
        success_count += 1
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    if success_count > 0:
        await msg.answer(t("pdf_ready", lang))


@router.message(F.text.in_({t("btn_university", "ru"), t("btn_university", "en")}))
async def btn_university(msg: Message):
    """Выбор вуза"""
    user_data = await get_or_create_user(msg.from_user.id)
    lang = get_lang(user_data)
    await _show_screen(
        msg,
        t("scenario_university", lang),
        kb=scenario_info_kb("university", lang),
    )


@router.message(F.text.in_({t("btn_job", "ru"), t("btn_job", "en")}))
async def btn_job(msg: Message):
    """Поиск работы"""
    user_data = await get_or_create_user(msg.from_user.id)
    lang = get_lang(user_data)
    await _show_screen(
        msg,
        t("scenario_job", lang),
        kb=scenario_info_kb("job", lang),
    )


@router.message(F.text.in_({t("btn_adaptation", "ru"), t("btn_adaptation", "en")}))
async def btn_adaptation(msg: Message):
    """Адаптация в компании"""
    user_data = await get_or_create_user(msg.from_user.id)
    lang = get_lang(user_data)
    await _show_screen(
        msg,
        t("scenario_adaptation", lang),
        kb=scenario_info_kb("adaptation", lang),
    )


@router.callback_query(F.data == "back_to_menu")
async def cb_back_to_menu(cb: CallbackQuery):
    """Возврат в главное меню — одно edit, без дубля"""
    user_data = await get_or_create_user(cb.from_user.id)
    lang = get_lang(user_data)
    text = f"{t('welcome_msg', lang)}\n\n{t('choose_scenario', lang)}"
    try:
        await cb.message.edit_text(text, reply_markup=None, parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, parse_mode="HTML")
    await cb.answer()


@router.message(F.text.in_({t("btn_progress", "ru"), t("btn_progress", "en")}))
async def btn_progress(msg: Message):
    """Показать статистику"""
    user_data = await get_or_create_user(msg.from_user.id)
    lang = get_lang(user_data)
    stats = await get_user_stats(msg.from_user.id)

    if stats["total_sessions"] == 0:
        await _show_screen(
            msg,
            f"{t('progress_header', lang)}\n\n{t('progress_empty', lang)}",
            kb=progress_kb(lang),
        )
        return

    text = f"{t('progress_header', lang)}\n\n"
    text += t("progress_sessions", lang, n=stats['total_sessions']) + "\n"
    text += t("progress_avg", lang, n=stats['avg_score']) + "\n\n"

    if stats["scenarios"]:
        text += t("progress_by_scenario", lang) + "\n"
        for scenario, data in stats["scenarios"].items():
            name = {
                "university": t("btn_university", lang),
                "job": t("btn_job", lang),
                "adaptation": t("btn_adaptation", lang),
            }.get(scenario, scenario)
            text += t("progress_scenario_line", lang, name=name, sessions=data['sessions'], avg=data['avg_score']) + "\n"

    await _show_screen(msg, text, kb=progress_kb(lang))


@router.message(F.text, StateFilter(None), ~F.text.in_(KNOWN_BUTTONS))
async def fallback_handler(msg: Message):
    """Неизвестные текстовые сообщения — всегда через AI"""
    user_id = msg.from_user.id
    user_data = await get_or_create_user(user_id)
    lang = get_lang(user_data)
    voice_enabled = user_data.get("voice_enabled", 0) == 1
    scenario = user_data.get("current_scenario", "university")

    await msg.bot.send_chat_action(msg.chat.id, "typing")
    from bot.core.scenarios import answer_info_question
    clean_text = _sanitize_input(msg.text)
    answer = await answer_info_question(clean_text, scenario, user_id=user_id, lang=lang)

    if lang != "ru":
        from bot.utils.translator import translate_text
        answer = await translate_text(answer, target_lang=lang)

    if voice_enabled:
        voice_file = await text_to_speech(answer)
        try:
            if voice_file:
                await msg.answer_voice(FSInputFile(voice_file))
                sent = await msg.answer(t("voice_text_prefix", lang, text=answer), parse_mode="HTML")
                try:
                    _remember(msg.chat.id, getattr(sent, "message_id", None))
                except Exception:
                    pass
            else:
                sent = await msg.answer(answer, parse_mode="HTML")
                try:
                    _remember(msg.chat.id, getattr(sent, "message_id", None))
                except Exception:
                    pass
        finally:
            if voice_file and os.path.exists(voice_file):
                os.remove(voice_file)
    else:
        sent = await msg.answer(answer, parse_mode="HTML")
        try:
            _remember(msg.chat.id, getattr(sent, "message_id", None))
        except Exception:
            pass

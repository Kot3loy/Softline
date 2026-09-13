"""Хендлеры старта — приветствие, главное меню, настройки, команды."""

import os
import logging
import asyncio
from aiogram import Router, F

logger = logging.getLogger(__name__)
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart, Command, StateFilter

from bot.utils.keyboards import main_menu_kb, scenario_info_kb, settings_kb
from bot.utils.voice import text_to_speech
from bot.core.ai_engine import _sanitize_input
from bot.database.db import get_or_create_user, get_user_stats, update_user

router = Router()

# кнопки меню чтобы fallback не перехватывал
KNOWN_BUTTONS = {
    "🎓 Выбор вуза", "💼 Поиск работы", "🤝 Адаптация в компании",
    "📊 Прогресс", "⚙️ Настройки",
}

# приветствие — первое что видит пользователь
WELCOME = (
    "👋 Привет! Я — твой <b>AI-наставник</b> от Softline.\n\n"
    "Помогу тебе с выбором вуза, поиском работы и адаптацией в компании.\n\n"
    "Выбери сценарий, чтобы начать:"
)

# о боте — всё в одном: что умеет, как пользоваться, дисклеймер
ABOUT_TEXT = (
    "ℹ️ <b>О боте</b>\n\n"
    "🤖 <b>AI-наставник</b> — telegram-бот для старшеклассников и молодых специалистов.\n\n"
    "📌 <b>Что умею:</b>\n"
    "• Помогаю с выбором вуза\n"
    "• Готовлю к собеседованиям\n"
    "• Помогаю адаптироваться на новой работе\n"
    "• Проверяю знания в режиме экзаменатора\n"
    "• Говорю голосом (включи в настройках)\n"
    "• Составляю PDF-отчёты (/export)\n\n"
    "💡 <b>Как пользоваться:</b>\n"
    "• Выбери сценарий в меню\n"
    "• Задавай вопросы — отвечу\n"
    "• В экзаменаторе отвечай на задания — дам обратную связь\n"
    "• Отправляй голосовые сообщения — отвечу голосом\n\n"
    "⚙️ <b>Настройки:</b> переключай голос\n"
    "📊 <b>Прогресс:</b> смотри статистику\n"
    "📥 <b>/export:</b> скачай PDF-отчёт\n\n"
    "👨‍💻 <b>Создан для:</b> SK Kids Challenge от Softline\n"
    "🔧 <b>Технологии:</b> Python, aiogram, GigaChat, edge-tts\n\n"
    "⚠️ <b>Дисклеймер:</b> рекомендации носят информационный характер "
    "и не заменяют официальные требования вузов и работодателей. "
    "Всегда проверяйте актуальную информацию на официальных сайтах."
)


@router.message(CommandStart())
async def cmd_start(msg: Message):
    """Приветствие"""
    await get_or_create_user(
        user_id=msg.from_user.id,
        username=msg.from_user.username,
        first_name=msg.from_user.first_name,
        last_name=msg.from_user.last_name,
    )
    await msg.answer(WELCOME, reply_markup=main_menu_kb(), parse_mode="HTML")


@router.message(Command("help"))
@router.message(Command("disclaimer"))
async def cmd_help(msg: Message):
    """Справка и дисклеймер — одно и то же"""
    await msg.answer(ABOUT_TEXT, parse_mode="HTML")


@router.message(F.text == "⚙️ Настройки")
async def btn_settings(msg: Message):
    """Меню настроек"""
    user_data = await get_or_create_user(msg.from_user.id)
    voice_enabled = user_data.get("voice_enabled", 0) == 1
    await msg.answer(
        "⚙️ <b>Настройки</b>",
        reply_markup=settings_kb(voice_enabled),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "settings_voice")
async def cb_settings_voice(cb: CallbackQuery):
    """Переключение голоса"""
    user_data = await get_or_create_user(cb.from_user.id)
    new_value = 0 if user_data.get("voice_enabled", 0) == 1 else 1
    await update_user(cb.from_user.id, voice_enabled=new_value)

    voice_enabled = new_value == 1
    await cb.message.edit_reply_markup(reply_markup=settings_kb(voice_enabled))
    status = "включён" if voice_enabled else "выключен"
    await cb.answer(f"Голос {status}!", show_alert=True)


@router.callback_query(F.data == "settings_about")
async def cb_settings_about(cb: CallbackQuery):
    """О боте"""
    await cb.message.answer(ABOUT_TEXT, parse_mode="HTML")
    await cb.answer()


@router.message(Command("export"))
async def cmd_export(msg: Message):
    """Команда /export — генерация PDF-отчёта"""
    from bot.database.db import get_case_answers
    from bot.utils.pdf_export import generate_report

    stats = await get_user_stats(msg.from_user.id)

    if not stats.get("scenarios"):
        await msg.answer(
            "📊 У тебя пока нет результатов.\n"
            "Пройди хотя бы одно задание, чтобы я мог сгенерировать отчёт."
        )
        return

    await msg.answer("📥 Генерирую отчёт...")

    success_count = 0
    for scenario, data in stats["scenarios"].items():
        if data["sessions"] > 0:
            case_answers = await get_case_answers(msg.from_user.id, scenario)
            results = [
                {"score": a["score"], "feedback": a.get("feedback", "")}
                for a in case_answers
            ] if case_answers else [
                {"score": data["avg_score"], "feedback": "Средний балл по сценарию"}
            ]
            try:
                report_path = await asyncio.to_thread(
                    generate_report, msg.from_user.id, scenario, results, case_answers
                )
                await msg.answer_document(
                    FSInputFile(report_path),
                    caption=f"📄 Отчёт: {scenario}",
                )
                success_count += 1
                # Удаляем PDF после отправки
                try:
                    if os.path.exists(report_path):
                        os.remove(report_path)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Ошибка генерации PDF: {e}")
                await msg.answer(f"❌ Не удалось сгенерировать отчёт для {scenario}")

    if success_count > 0:
        await msg.answer(
            "✅ Отчёт готов!\n\n"
            "⚠️ Рекомендации носят информационный характер и не заменяют "
            "официальные требования вузов и работодателей."
        )


@router.message(F.text == "🎓 Выбор вуза")
async def btn_university(msg: Message):
    """Выбор вуза"""
    await msg.answer(
        "🎓 <b>Сценарий: Выбор вуза</b>\n\n"
        "Помогу тебе выбрать вуз, разобраться с поступлением и специальностями.\n\n"
        "Что тебя интересует?",
        reply_markup=scenario_info_kb("university"),
        parse_mode="HTML",
    )


@router.message(F.text == "💼 Поиск работы")
async def btn_job(msg: Message):
    """Поиск работы"""
    await msg.answer(
        "💼 <b>Сценарий: Поиск работы</b>\n\n"
        "Помогу подготовиться к собеседованию, составить резюме и найти стажировку.\n\n"
        "Что тебе нужно?",
        reply_markup=scenario_info_kb("job"),
        parse_mode="HTML",
    )


@router.message(F.text == "🤝 Адаптация в компании")
async def btn_adaptation(msg: Message):
    """Адаптация в компании"""
    await msg.answer(
        "🤝 <b>Сценарий: Адаптация в компании</b>\n\n"
        "Помогу адаптироваться на новом месте, понять корпоративную культуру и общаться с коллегами.\n\n"
        "Начнём?",
        reply_markup=scenario_info_kb("adaptation"),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "back_to_menu")
async def cb_back_to_menu(cb: CallbackQuery):
    """Возврат в главное меню"""
    try:
        await cb.message.edit_text(WELCOME, reply_markup=None, parse_mode="HTML")
    except Exception:
        # Если edit_text не работает (не-text сообщение) — отправляем новое
        pass
    await cb.message.answer("Выбери сценарий:", reply_markup=main_menu_kb())
    await cb.answer()


@router.message(F.text == "📊 Прогресс")
async def btn_progress(msg: Message):
    """Показать статистику"""
    stats = await get_user_stats(msg.from_user.id)

    if stats["total_sessions"] == 0:
        await msg.answer(
            "📊 <b>Твой прогресс</b>\n\n"
            "Пока тут пусто — ты только начинаешь!\n"
            "Пройди хотя бы одно задание, и я покажу статистику.",
            parse_mode="HTML",
        )
        return

    text = "📊 <b>Твой прогресс</b>\n\n"
    text += f"Всего сессий: {stats['total_sessions']}\n"
    text += f"Средний балл: {stats['avg_score']}\n\n"

    if stats["scenarios"]:
        text += "<b>По сценариям:</b>\n"
        for scenario, data in stats["scenarios"].items():
            name = {
                "university": "🎓 Выбор вуза",
                "job": "💼 Поиск работы",
                "adaptation": "🤝 Адаптация",
            }.get(scenario, scenario)
            text += f"  {name}: {data['sessions']} сессий, средний {data['avg_score']}\n"

    await msg.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")


@router.message(F.text, StateFilter(None), ~F.text.in_(KNOWN_BUTTONS))
async def fallback_handler(msg: Message):
    """Неизвестные текстовые сообщения"""
    user_id = msg.from_user.id
    user_data = await get_or_create_user(user_id)
    voice_enabled = user_data.get("voice_enabled", 0) == 1
    scenario = user_data.get("current_scenario", "university")

    if voice_enabled:
        await msg.bot.send_chat_action(msg.chat.id, "typing")
        from bot.core.scenarios import answer_info_question
        clean_text = _sanitize_input(msg.text)
        answer = await answer_info_question(clean_text, scenario, user_id=user_id)
        voice_file = await text_to_speech(answer)
        try:
            if voice_file:
                await msg.answer_voice(FSInputFile(voice_file))
                await msg.answer(f"📝 <b>Текст:</b>\n{answer}", parse_mode="HTML")
            else:
                await msg.answer(answer, parse_mode="HTML")
        finally:
            if voice_file and os.path.exists(voice_file):
                os.remove(voice_file)
    else:
        await msg.answer(
            "🤔 Я не совсем понял.\n\n"
            "Используй кнопки меню или напиши /help, чтобы узнать, что я умею.",
            reply_markup=main_menu_kb(),
        )

"""Хендлер режима экзаменатора — генерация и оценка заданий."""

import time
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.utils.keyboards import exam_cases_kb, case_answer_kb, choice_answer_kb
from bot.core.ai_engine import generate_case, evaluate_answer, check_answer_relevance
from bot.core.adaptive import record_error, get_weak_areas, get_recommendations
from bot.core.common_mistakes import find_mistakes
from bot.database.db import create_session, end_session, save_case_answer, update_user

router = Router()

EXAM_DISCLAIMER = (
    "\n\n⚠️ Рекомендации носят информационный характер и не заменяют "
    "официальные требования вузов и работодателей."
)

SESSION_TTL = 1800  # 30 минут


def pluralize(n: int, one: str, few: str, many: str) -> str:
    """Склонение существительных после числительных (русский язык)"""
    mod10 = n % 10
    mod100 = n % 100
    if 11 <= mod100 <= 19:
        return many
    if mod10 == 1:
        return one
    if 2 <= mod10 <= 4:
        return few
    return many


class ExamState(StatesGroup):
    """Состояния экзаменатора"""
    waiting_for_answer = State()
    session_active = State()


# Сессии экзамена (в памяти)
MAX_EXAM_SESSIONS = 1000  # максимум сессий одновременно
exam_sessions = {}  # user_id -> {scenario, cases, current, session_id, answers, timestamp}


def _cleanup_expired_sessions():
    """Удалить сессии старше SESSION_TTL или при превышении лимита"""
    now = time.time()
    expired = [uid for uid, s in exam_sessions.items() if now - s.get("timestamp", 0) > SESSION_TTL]
    for uid in expired:
        del exam_sessions[uid]
    # Если всё ещё слишком много — удаляем самые старые
    if len(exam_sessions) > MAX_EXAM_SESSIONS:
        sorted_sessions = sorted(exam_sessions.items(), key=lambda x: x[1].get("timestamp", 0))
        to_remove = len(exam_sessions) - MAX_EXAM_SESSIONS
        for uid, _ in sorted_sessions[:to_remove]:
            del exam_sessions[uid]


@router.callback_query(F.data.startswith("exam_"))
async def cb_examiner_mode(cb: CallbackQuery):
    """Режим экзаменатора — выбор количества кейсов"""
    scenario = cb.data.replace("exam_", "")
    await update_user(cb.from_user.id, current_scenario=scenario)

    await cb.message.edit_text(
        "🎯 <b>Режим экзаменатора</b>\n\n"
        "Я предложу тебе проблемные задания.\n"
        "Ты отвечаешь — я даю обратную связь.\n\n"
        "Сколько заданий за сессию?",
        reply_markup=exam_cases_kb(),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data.startswith("cases_"))
async def cb_start_exam(cb: CallbackQuery, state: FSMContext):
    """Начало экзамена — генерация первого кейса"""
    try:
        count = int(cb.data.replace("cases_", ""))
    except ValueError:
        await cb.answer("Ошибка", show_alert=True)
        return

    if count not in (3, 5, 10):
        await cb.answer("Ошибка", show_alert=True)
        return

    user_id = cb.from_user.id

    from bot.database.db import get_or_create_user
    user_data = await get_or_create_user(user_id)
    scenario = user_data.get("current_scenario", "university")

    session_id = await create_session(user_id, scenario, "examiner", count)

    await cb.answer()

    await cb.message.edit_text(
        f"🎯 Начинаем! Генерирую {count} {pluralize(count, 'задание', 'задания', 'заданий')}...",
        reply_markup=None,
        parse_mode="HTML",
    )

    weak_areas = get_weak_areas(user_id, scenario)

    cases = []
    for i in range(count):
        # Чередуем: каждое 3-е задание — choice, остальные open
        case_type = "choice" if (i % 3 == 1) else "open"
        case = await generate_case(scenario, weak_areas=weak_areas if i == 0 else None, case_type=case_type, user_id=user_id)
        cases.append(case)

    exam_sessions[user_id] = {
        "scenario": scenario,
        "cases": cases,
        "current": 0,
        "total": count,
        "session_id": session_id,
        "answers": [],
        "scores": [],
        "timestamp": time.time(),
    }

    case = cases[0]
    if case.get("type") == "choice":
        await cb.message.answer(
            f"📋 <b>Задание 1 из {count}</b>\n\n"
            f"{case['situation']}\n\n"
            f"❓ <b>{case['question']}</b>",
            reply_markup=choice_answer_kb(case.get("options", []), 1, count),
            parse_mode="HTML",
        )
    else:
        await cb.message.answer(
            f"📋 <b>Задание 1 из {count}</b>\n\n"
            f"{case['situation']}\n\n"
            f"❓ <b>{case['question']}</b>",
            reply_markup=case_answer_kb(1, count),
            parse_mode="HTML",
        )
    await state.set_state(ExamState.waiting_for_answer)


@router.callback_query(F.data == "next_case")
async def cb_next_case(cb: CallbackQuery, state: FSMContext):
    """Кнопка 'Следующее задание'"""
    _cleanup_expired_sessions()
    user_id = cb.from_user.id
    session = exam_sessions.get(user_id)

    if not session:
        await cb.answer("Сессия не найдена. Начни заново.", show_alert=True)
        return

    await cb.answer()

    session["current"] += 1
    current_idx = session["current"]
    if current_idx >= session["total"]:
        return

    case = session["cases"][current_idx]
    if case.get("type") == "choice":
        await cb.message.answer(
            f"📋 <b>Задание {current_idx + 1} из {session['total']}</b>\n\n"
            f"{case['situation']}\n\n"
            f"❓ <b>{case['question']}</b>",
            reply_markup=choice_answer_kb(case.get("options", []), current_idx + 1, session["total"]),
            parse_mode="HTML",
        )
    else:
        await cb.message.answer(
            f"📋 <b>Задание {current_idx + 1} из {session['total']}</b>\n\n"
            f"{case['situation']}\n\n"
            f"❓ <b>{case['question']}</b>",
            reply_markup=case_answer_kb(current_idx + 1, session["total"]),
            parse_mode="HTML",
        )
    await state.set_state(ExamState.waiting_for_answer)


@router.callback_query(F.data.startswith("answer_choice_"))
async def cb_answer_choice(cb: CallbackQuery, state: FSMContext):
    """Обработка выбора ответа (кнопка A/B/C/D)"""
    _cleanup_expired_sessions()
    user_id = cb.from_user.id
    session = exam_sessions.get(user_id)

    if not session:
        await cb.answer("Сессия не найдена. Начни заново.", show_alert=True)
        return

    current_idx = session["current"]
    if current_idx >= len(session["cases"]):
        await cb.answer("Все задания уже пройдены", show_alert=True)
        return

    case = session["cases"][current_idx]
    if case.get("type") != "choice":
        await cb.answer("Это не задание с выбором", show_alert=True)
        return

    # Парсим индекс выбранного варианта
    try:
        chosen_idx = int(cb.data.replace("answer_choice_", ""))
    except ValueError:
        await cb.answer("Ошибка", show_alert=True)
        return

    correct_idx = case.get("correct", 0)
    options = case.get("options", [])
    is_correct = chosen_idx == correct_idx

    # Формируем оценку
    if is_correct:
        score = 10
        feedback = f"✅ Правильно! {case.get('explanation', '')}"
    else:
        score = 2
        feedback = (
            f"❌ Неправильно.\n"
            f"Твой ответ: {options[chosen_idx] if chosen_idx < len(options) else '?'}\n"
            f"Правильный: {options[correct_idx] if correct_idx < len(options) else '?'}\n"
            f"{case.get('explanation', '')}"
        )

    session["answers"].append({
        "case_idx": current_idx,
        "user_answer": f"[Выбор: {options[chosen_idx] if chosen_idx < len(options) else '?'}]",
        "evaluation": {"score": score, "feedback": feedback},
    })
    session["scores"].append(score)

    case_id = f"{session['scenario']}_{current_idx + 1}"
    await asyncio.to_thread(record_error, user_id, case_id, session["scenario"], score)

    await save_case_answer(
        session_id=session["session_id"],
        user_id=user_id,
        case_id=case_id,
        scenario=session["scenario"],
        user_answer=f"[Выбор: {options[chosen_idx] if chosen_idx < len(options) else '?'}]",
        score=score,
        feedback=feedback,
    )

    answered = len(session["scores"])
    total = session["total"]
    text = f"📊 <b>Оценка: {score}/10</b>\n\n{feedback}\n\n"
    text += f"📋 Выполнено: {answered}/{total}\n"
    text += EXAM_DISCLAIMER

    next_idx = current_idx + 1

    await cb.answer()

    if next_idx >= session["total"]:
        avg_score = sum(session["scores"]) / len(session["scores"]) if session["scores"] else 0
        if not session.get("_ended"):
            await end_session(session["session_id"], len(session["scores"]), avg_score)
            session["_ended"] = True

        recommendations = get_recommendations(user_id, session["scenario"])

        result_text = "🎯 <b>Сессия завершена!</b>\n\n"
        result_text += f"Выполнено: {answered}/{total}\n"
        result_text += f"Средний балл: {avg_score:.1f}/10\n\n"

        if recommendations:
            result_text += "<b>Рекомендации:</b>\n"
            for r in recommendations:
                result_text += f"  • {r}\n"

        result_text += EXAM_DISCLAIMER

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Экспорт в PDF", callback_data="export_pdf")],
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_menu")],
        ])

        await cb.message.answer(result_text, reply_markup=kb, parse_mode="HTML")
        await state.clear()
        exam_sessions.pop(user_id, None)
    else:
        next_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="▶ Следующее задание", callback_data="next_case")]
        ])
        await cb.message.answer(text, reply_markup=next_kb, parse_mode="HTML")


@router.callback_query(F.data == "show_results")
async def cb_show_results(cb: CallbackQuery, state: FSMContext):
    """Кнопка 'Результаты' — показать итоги сессии"""
    user_id = cb.from_user.id
    session = exam_sessions.get(user_id)

    if not session:
        await cb.answer("Сессия не найдена", show_alert=True)
        return

    await cb.answer()
    await state.clear()

    answered = len(session["scores"])
    total = session["total"]
    avg_score = sum(session["scores"]) / len(session["scores"]) if session["scores"] else 0

    if session.get("session_id") and not session.get("_ended"):
        await end_session(session["session_id"], answered, avg_score)
        session["_ended"] = True

    weak_areas = get_weak_areas(user_id, session["scenario"])
    recommendations = get_recommendations(user_id, session["scenario"])

    text = "🎯 <b>Сессия завершена!</b>\n\n"
    text += f"Выполнено: {answered}/{total}\n"
    text += f"Средний балл: {avg_score:.1f}/10\n\n"

    if recommendations:
        text += "<b>Рекомендации:</b>\n"
        for r in recommendations:
            text += f"  • {r}\n"

    text += EXAM_DISCLAIMER

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Экспорт в PDF", callback_data="export_pdf")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_menu")],
    ])

    await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(ExamState.waiting_for_answer)
async def handle_exam_answer(msg: Message, state: FSMContext):
    """Обработка ответа на кейс (свободный текст)"""
    _cleanup_expired_sessions()
    user_id = msg.from_user.id
    session = exam_sessions.get(user_id)

    if not session:
        await state.clear()
        await msg.answer("Сессия экзамена завершена. Начни заново из главного меню.")
        return

    current_idx = session["current"]
    if current_idx >= len(session["cases"]):
        await state.clear()
        await msg.answer("Все задания уже пройдены.")
        return

    case = session["cases"][current_idx]

    # Пропускаем choice-задания в текстовом обработчике (они через callback)
    if case.get("type") == "choice":
        await msg.answer("Это задание с выбором ответа. Нажми на кнопку с вариантом.")
        return

    await msg.bot.send_chat_action(msg.chat.id, "typing")

    # Проверяем релевантность ответа
    relevance = await check_answer_relevance(msg.text, case, user_id=user_id)
    if not relevance.get("relevant", True):
        await msg.answer(
            "⚠️ Твой ответ не совсем по теме задания.\n"
            f"Причина: {relevance.get('reason', 'не по теме')}\n\n"
            "Попробуй ответить ещё раз или нажми «Следующее задание»."
        )
        return

    evaluation = await evaluate_answer(msg.text, case, user_id=user_id)

    score = evaluation.get("score", 5)
    feedback = evaluation.get("feedback", "")
    strengths = evaluation.get("strengths", [])
    weaknesses = evaluation.get("weaknesses", [])

    session["answers"].append({
        "case_idx": current_idx,
        "user_answer": msg.text,
        "evaluation": evaluation,
    })
    session["scores"].append(score)

    case_id = f"{session['scenario']}_{current_idx + 1}"
    await asyncio.to_thread(record_error, user_id, case_id, session["scenario"], score)

    await save_case_answer(
        session_id=session["session_id"],
        user_id=user_id,
        case_id=case_id,
        scenario=session["scenario"],
        user_answer=msg.text,
        score=score,
        feedback=feedback,
    )

    text = f"📊 <b>Оценка: {score}/10</b>\n\n"
    text += f"{feedback}\n\n"

    # Проверяем типовые ошибки
    mistakes = find_mistakes(msg.text)
    if mistakes:
        text += "🔍 <b>Типичные ошибки:</b>\n"
        for m in mistakes[:2]:  # Максимум 2 ошибки чтобы не перегружать
            text += f"  • {m['error']}\n"
            text += f"    💡 Совет: {m['advice']}\n"

    if strengths:
        text += "✅ <b>Сильные стороны:</b>\n"
        for s in strengths:
            text += f"  • {s}\n"

    if weaknesses:
        text += "\n⚠️ <b>Слабые стороны:</b>\n"
        for w in weaknesses:
            text += f"  • {w}\n"

    example = evaluation.get("example_answer", "")
    if example:
        text += f"\n💡 <b>Пример удачного ответа:</b>\n{example}\n"

    # Источник из оценки
    source = evaluation.get("source", "")
    if source:
        text += f"\n📚 <b>Источник:</b> {source}\n"

    answered = len(session["scores"])
    total = session["total"]
    text += f"\n📋 Выполнено: {answered}/{total}\n"
    text += EXAM_DISCLAIMER

    next_idx = current_idx + 1

    if next_idx >= session["total"]:
        avg_score = sum(session["scores"]) / len(session["scores"]) if session["scores"] else 0
        if not session.get("_ended"):
            await end_session(session["session_id"], len(session["scores"]), avg_score)
            session["_ended"] = True

        weak_areas = get_weak_areas(user_id, session["scenario"])
        recommendations = get_recommendations(user_id, session["scenario"])

        result_text = "🎯 <b>Сессия завершена!</b>\n\n"
        result_text += f"Выполнено: {answered}/{total}\n"
        result_text += f"Средний балл: {avg_score:.1f}/10\n\n"

        if recommendations:
            result_text += "<b>Рекомендации:</b>\n"
            for r in recommendations:
                result_text += f"  • {r}\n"

        result_text += EXAM_DISCLAIMER

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Экспорт в PDF", callback_data="export_pdf")],
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_menu")],
        ])

        await msg.answer(result_text, reply_markup=kb, parse_mode="HTML")
        await state.clear()
        exam_sessions.pop(user_id, None)
    else:
        next_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="▶ Следующее задание", callback_data="next_case")]
        ])
        await msg.answer(text, reply_markup=next_kb, parse_mode="HTML")

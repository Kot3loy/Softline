# экзаменатор: бот генерирует задания, юзер отвечает, ai оценивает

import time
import asyncio
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.translations import t
from bot.utils.keyboards import exam_cases_kb, case_answer_kb, choice_answer_kb
from bot.utils.lang import get_lang
from bot.core.ai_engine import generate_case, evaluate_answer, _strip_markdown
from bot.core.adaptive import record_error, get_weak_areas, get_recommendations, get_clarifying_question
from bot.core.common_mistakes import find_mistakes
from bot.database.db import create_session, end_session, save_case_answer, update_user, get_or_create_user
from bot.handlers.start import _replace_card

logger = logging.getLogger(__name__)

router = Router()

SESSION_TTL = 1800  # 30 минут


class ExamState(StatesGroup):
    waiting_for_answer = State()
    session_active = State()


# Сессии экзамена (в памяти)
MAX_EXAM_SESSIONS = 1000
exam_sessions: dict[int, dict] = {}  # user_id -> {scenario, cases, current, session_id, answers, timestamp}


def _cleanup_expired_sessions():
    # сессии висят в памяти — удаляю те что неактивны больше 30 минут
    now = time.time()
    expired = [uid for uid, s in exam_sessions.items() if now - s.get("timestamp", 0) > SESSION_TTL]
    for uid in expired:
        del exam_sessions[uid]
    if len(exam_sessions) > MAX_EXAM_SESSIONS:
        sorted_sessions = sorted(exam_sessions.items(), key=lambda x: x[1].get("timestamp", 0))
        to_remove = len(exam_sessions) - MAX_EXAM_SESSIONS
        for uid, _ in sorted_sessions[:to_remove]:
            del exam_sessions[uid]


async def _translate_if_needed(text: str, lang: str) -> str:
    # ai думает на русском, а юзеру отвечаем на его языке
    if lang == "ru" or not text:
        return text
    from bot.utils.translator import translate_text
    return await translate_text(text, target_lang=lang)


async def _drop_message(bot, chat_id, message_id):
    # удаляем сообщение с заданием, чтобы чат не засорялся.
    # сообщение могли удалить руками — тогда просто молча идём дальше
    if not message_id or not chat_id:
        return
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception as e:
        logger.debug(f"Не удалось удалить сообщение {message_id}: {e}")


async def _drop_case(session: dict, bot):
    # убрать текущее задание и забыть его id
    await _drop_message(bot, session.get("chat_id"), session.get("case_msg_id"))
    session["case_msg_id"] = None


async def abandon_exam(user_id: int):
    # юзер вышел из экзамена не до конца — записываем реальные цифры,
    # иначе сессия навсегда остаётся незавершённой и не попадает в отчёт
    session = exam_sessions.pop(user_id, None)
    if not session:
        return

    scores = session.get("scores") or []
    answered = len(scores)
    avg_score = sum(scores) / answered if answered else 0
    session_id = session.get("session_id")

    if session_id and not session.get("_ended"):
        try:
            await end_session(session_id, answered, avg_score)
        except Exception as e:
            logger.warning(f"Не удалось закрыть сессию {session_id}: {e}")
        else:
            logger.info(f"Экзамен закрыт досрочно: user={user_id}, отвечено {answered}")


async def _finalize_exam(user_id: int, session: dict, message, lang: str):
    # финал: считаем средний балл, сохраняем сессию в бд, показываем итоги
    # на всякий случай убираем последнее задание, если оно ещё висит
    await _drop_case(session, getattr(message, "bot", None))
    answered = len(session["scores"])
    avg_score = sum(session["scores"]) / len(session["scores"]) if session["scores"] else 0

    if session.get("session_id") and not session.get("_ended"):
        await end_session(session["session_id"], answered, avg_score)
        session["_ended"] = True

    recommendations = get_recommendations(user_id, session["scenario"], lang)

    result_text = f"{t('exam_complete', lang)}\n\n"
    result_text += t("exam_done", lang, n=answered, total=session["total"]) + "\n"
    result_text += t("exam_avg", lang, n=f"{avg_score:.1f}") + "\n\n"

    if recommendations:
        result_text += t("exam_recommendations", lang) + "\n"
        for r in recommendations:
            result_text += f"  • {r}\n"

    # уточняющий вопрос по самой слабой теме (появляется с 2-й сессии)
    clarify = get_clarifying_question(user_id, session["scenario"], lang)
    if clarify:
        result_text += f"\n\n{clarify}"

    # Дисклеймер — рекомендации носят информационный характер
    result_text += f"\n\n{t('disclaimer', lang)}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("exam_export", lang), callback_data="export_pdf")],
        [InlineKeyboardButton(text=t("btn_back", lang), callback_data="back_to_menu")],
    ])

    await message.answer(result_text, reply_markup=kb, parse_mode="HTML")
    exam_sessions.pop(user_id, None)


@router.callback_query(F.data.startswith("exam_"))
async def cb_examiner_mode(cb: CallbackQuery):
    # юзер нажал "экзаменатор" — показываю выбор количества заданий
    scenario = cb.data.replace("exam_", "")
    await update_user(cb.from_user.id, current_scenario=scenario)

    user_data = await get_or_create_user(cb.from_user.id)
    lang = get_lang(user_data)

    if not cb.message:
        return
    await _replace_card(
        cb.message,
        f"{t('exam_header', lang)}\n\n{t('exam_intro', lang)}",
        kb=exam_cases_kb(lang),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("cases_"))
async def cb_start_exam(cb: CallbackQuery, state: FSMContext):
    # генерирую все задания сразу (чтобы потом не ждать ai между кейсами)
    try:
        count = int(cb.data.replace("cases_", ""))
    except ValueError:
        await cb.answer("Error", show_alert=True)
        return

    if count not in (3, 5, 10):
        await cb.answer("Error", show_alert=True)
        return

    user_id = cb.from_user.id
    user_data = await get_or_create_user(user_id)
    lang = get_lang(user_data)
    scenario = user_data.get("current_scenario", "university")

    session_id = await create_session(user_id, scenario, "examiner", count)
    await cb.answer()

    # экзамен — новая сессия, инфо-история больше не нужна
    from bot.core.ai_engine import clear_history
    await clear_history(user_id)

    await _replace_card(cb.message, t("exam_start", lang, n=count), kb=None)

    weak_areas = get_weak_areas(user_id, scenario)

    cases = []
    for i in range(count):
        case_type = "choice" if (i % 3 == 1) else "open"
        case = await generate_case(scenario, weak_areas=weak_areas if i == 0 else None, case_type=case_type)
        # Переводим кейс если нужно
        if lang != "ru":
            case = dict(case)
            for key in ("situation", "question", "hint"):
                if key in case and case[key]:
                    case[key] = await _translate_if_needed(case[key], lang)
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
        "chat_id": cb.message.chat.id,
        "case_msg_id": None,
        "feedback_msg_id": None,
    }

    case = cases[0]
    task_header = t("exam_task", lang, n=1, total=count)
    question_text = t("exam_question", lang, text=case['question'])

    if case.get("type") == "choice":
        sent = await cb.message.answer(
            f"{task_header}\n\n{case['situation']}\n\n{question_text}",
            reply_markup=choice_answer_kb(case.get("options", [])),
            parse_mode="HTML",
        )
    else:
        sent = await cb.message.answer(
            f"{task_header}\n\n{case['situation']}\n\n{question_text}",
            reply_markup=case_answer_kb(1, count, lang),
            parse_mode="HTML",
        )
    exam_sessions[user_id]["case_msg_id"] = getattr(sent, "message_id", None)
    await state.set_state(ExamState.waiting_for_answer)


@router.callback_query(F.data == "next_case")
async def cb_next_case(cb: CallbackQuery, state: FSMContext):
    _cleanup_expired_sessions()
    user_id = cb.from_user.id
    session = exam_sessions.get(user_id)

    user_data = await get_or_create_user(user_id)
    lang = get_lang(user_data)

    if not session:
        await cb.answer(t("exam_session_not_found", lang), show_alert=True)
        return

    session["current"] += 1
    current_idx = session["current"]
    if current_idx >= session["total"]:
        await cb.answer(t("exam_all_done", lang), show_alert=True)
        return
    await cb.answer()

    # если текущее задание так и осталось без ответа — убираем его из чата
    await _drop_case(session, cb.bot)

    case = session["cases"][current_idx]
    task_header = t("exam_task", lang, n=current_idx + 1, total=session['total'])
    question_text = t("exam_question", lang, text=case['question'])

    if case.get("type") == "choice":
        sent = await cb.message.answer(
            f"{task_header}\n\n{case['situation']}\n\n{question_text}",
            reply_markup=choice_answer_kb(case.get("options", [])),
            parse_mode="HTML",
        )
    else:
        sent = await cb.message.answer(
            f"{task_header}\n\n{case['situation']}\n\n{question_text}",
            reply_markup=case_answer_kb(current_idx + 1, session["total"], lang),
            parse_mode="HTML",
        )
    session["case_msg_id"] = getattr(sent, "message_id", None)
    await state.set_state(ExamState.waiting_for_answer)


@router.callback_query(F.data.startswith("answer_choice_"))
async def cb_answer_choice(cb: CallbackQuery, state: FSMContext):
    _cleanup_expired_sessions()
    user_id = cb.from_user.id
    session = exam_sessions.get(user_id)

    user_data = await get_or_create_user(user_id)
    lang = get_lang(user_data)

    if not session:
        await cb.answer(t("exam_session_not_found", lang), show_alert=True)
        return

    current_idx = session["current"]
    if current_idx >= len(session["cases"]):
        await cb.answer(t("exam_all_done", lang), show_alert=True)
        return

    case = session["cases"][current_idx]
    if case.get("type") != "choice":
        await cb.answer(t("exam_not_choice", lang), show_alert=True)
        return

    try:
        chosen_idx = int(cb.data.replace("answer_choice_", ""))
    except ValueError:
        await cb.answer("Error", show_alert=True)
        return

    correct_idx = case.get("correct", 0)
    options = case.get("options", [])
    is_correct = chosen_idx == correct_idx

    if is_correct:
        score = 10
        feedback = await _translate_if_needed(
            f"✅ Правильно! {case.get('explanation', '')}", lang
        )
    else:
        score = 2
        your_answer = options[chosen_idx] if chosen_idx < len(options) else "?"
        correct_answer = options[correct_idx] if correct_idx < len(options) else "?"
        feedback = await _translate_if_needed(
            f"❌ Неправильно.\nТвой ответ: {your_answer}\nПравильный: {correct_answer}\n{case.get('explanation', '')}",
            lang,
        )

    session["answers"].append({
        "case_idx": current_idx,
        "user_answer": f"[Выбор: {options[chosen_idx] if chosen_idx < len(options) else '?'}]",
        "evaluation": {"score": score, "feedback": feedback},
    })
    session["scores"].append(score)

    case_id = f"{session['scenario']}_{current_idx + 1}"
    topic = case.get("situation") or case.get("question") or ""
    await asyncio.to_thread(record_error, user_id, case_id, session["scenario"], score, topic)

    await save_case_answer(
        session["session_id"],
        user_id,
        case_id,
        session["scenario"],
        f"[Выбор: {options[chosen_idx] if chosen_idx < len(options) else '?'}]",
        score,
        feedback,
    )

    answered = len(session["scores"])
    total = session["total"]
    text = f"{t('exam_score', lang, n=score)}\n\n{feedback}\n\n"
    text += t("exam_done", lang, n=answered, total=total)

    next_idx = current_idx + 1
    await cb.answer()

    # задание отработало — убираем его из чата, разбор остаётся
    await _drop_case(session, cb.bot)

    if next_idx >= session["total"]:
        await _finalize_exam(user_id, session, cb.message, lang)
        await state.clear()
    else:
        next_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("exam_next", lang), callback_data="next_case")]
        ])
        sent = await cb.message.answer(text, reply_markup=next_kb, parse_mode="HTML")
        session["feedback_msg_id"] = getattr(sent, "message_id", None)


@router.callback_query(F.data == "show_results")
async def cb_show_results(cb: CallbackQuery, state: FSMContext):
    user_id = cb.from_user.id
    session = exam_sessions.get(user_id)

    user_data = await get_or_create_user(user_id)
    lang = get_lang(user_data)

    if not session:
        await cb.answer(t("exam_session_not_found", lang), show_alert=True)
        return

    await cb.answer()
    await state.clear()
    await _finalize_exam(user_id, session, cb.message, lang)


async def _format_mistakes(mistakes: list, lang: str) -> str:
    # типовые ошибки хранятся в коде на русском — для английского переводим
    if not mistakes:
        return ""
    block = t("exam_typical_errors", lang) + "\n"
    for m in mistakes[:2]:
        error = await _translate_if_needed(m["error"], lang)
        advice = await _translate_if_needed(m["advice"], lang)
        block += f"  • {error}\n"
        block += f"    {t('exam_advice', lang, text=advice)}\n"
        if m.get("source"):
            block += f"    {t('exam_source', lang, text=m['source'])}\n"
    return block


@router.message(ExamState.waiting_for_answer)
async def handle_exam_answer(msg: Message, state: FSMContext):
    _cleanup_expired_sessions()
    user_id = msg.from_user.id
    session = exam_sessions.get(user_id)

    user_data = await get_or_create_user(user_id)
    lang = get_lang(user_data)

    if not session:
        await state.clear()
        await msg.answer(t("exam_session_not_found", lang))
        return

    current_idx = session["current"]
    if current_idx >= len(session["cases"]):
        await state.clear()
        await msg.answer(t("exam_all_done", lang))
        return

    case = session["cases"][current_idx]

    if case.get("type") == "choice":
        await msg.answer(t("exam_task_choice_text", lang))
        return

    await msg.bot.send_chat_action(msg.chat.id, "typing")

    # Переводим ответ пользователя в русский для AI
    user_answer_text = msg.text
    if lang != "ru":
        from bot.utils.translator import translate_text
        user_answer_text = await translate_text(user_answer_text, target_lang="ru")

    # Релевантность не блокирует: AI оценивает всегда, 0-2 = не по теме
    if len(user_answer_text.strip()) < 2:
        await msg.answer(t("exam_relevance_warning", lang, reason="слишком коротко"))
        return

    evaluation = await evaluate_answer(user_answer_text, case)

    score = evaluation.get("score", 5)
    # Убираем markdown из feedback и списков до перевода
    evaluation["feedback"] = _strip_markdown(evaluation.get("feedback", ""))
    evaluation["strengths"] = [_strip_markdown(s) for s in evaluation.get("strengths", [])]
    evaluation["weaknesses"] = [_strip_markdown(w) for w in evaluation.get("weaknesses", [])]
    feedback = await _translate_if_needed(evaluation["feedback"], lang)
    strengths = evaluation["strengths"][:2]
    weaknesses = evaluation["weaknesses"][:2]

    session["answers"].append({
        "case_idx": current_idx,
        "user_answer": msg.text,
        "evaluation": evaluation,
    })
    session["scores"].append(score)

    case_id = f"{session['scenario']}_{current_idx + 1}"
    topic = case.get("situation") or case.get("question") or ""
    await asyncio.to_thread(record_error, user_id, case_id, session["scenario"], score, topic)

    await save_case_answer(
        session["session_id"],
        user_id,
        case_id,
        session["scenario"],
        msg.text,
        score,
        feedback,
    )

    text = f"{t('exam_score', lang, n=score)}\n\n{feedback}\n\n"

    text += await _format_mistakes(find_mistakes(user_answer_text), lang)

    if strengths:
        text += t("exam_strengths", lang) + "\n"
        for s in strengths:
            text += f"  • {s}\n"

    if weaknesses:
        text += f"\n{t('exam_weaknesses', lang)}\n"
        for w in weaknesses:
            text += f"  • {w}\n"

    example = evaluation.get("example_answer", "")
    if example:
        example = await _translate_if_needed(example, lang)
        text += f"\n{t('exam_example', lang, text=example)}\n"

    source = evaluation.get("source", "")
    if source:
        text += f"\n{t('exam_source', lang, text=source)}\n"

    # Дисклеймер — рекомендации носят информационный характер
    text += f"\n\n{t('disclaimer', lang)}"

    answered = len(session["scores"])
    total = session["total"]
    text += f"\n{t('exam_done', lang, n=answered, total=total)}"

    next_idx = current_idx + 1

    # задание отработало — убираем текст задания, разбор остаётся
    await _drop_case(session, msg.bot)

    if next_idx >= session["total"]:
        await _finalize_exam(user_id, session, msg, lang)
        await state.clear()
    else:
        next_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("exam_next", lang), callback_data="next_case")]
        ])
        sent = await msg.answer(text, reply_markup=next_kb, parse_mode="HTML")
        session["feedback_msg_id"] = getattr(sent, "message_id", None)

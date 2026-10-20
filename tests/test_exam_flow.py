"""Сквозной сценарий экзамена: открытый → тест → открытый, финал и возврат в меню."""

import pytest
from unittest.mock import AsyncMock, patch

from bot.handlers import examiner
from bot.translations import t

UID = 123456789


def _open(situation="Открытая ситуация", question="Открытый вопрос?"):
    return {
        "type": "open",
        "situation": situation,
        "question": question,
        "good_answer_points": [],
        "common_mistakes": [],
    }


def _choice(situation="Ситуация с тестом", question="Что выбрать?"):
    return {
        "type": "choice",
        "situation": situation,
        "question": question,
        "options": ["420 рублей", "360 рублей", "240 рублей", "180 рублей"],
        "correct": 2,
        "explanation": "Скидка 30%",
    }


def _texts(mock):
    """Тексты, отправленные в чат (позиционный первый аргумент answer)."""
    return [call.args[0] for call in mock.answer.await_args_list if call.args]


def _deleted(mock):
    """Что просили удалить: [(chat_id, message_id), ...]"""
    return [call.args for call in mock.bot.delete_message.await_args_list]


def _kb(mock):
    return mock.answer.await_args.kwargs.get("reply_markup")


@pytest.mark.asyncio
async def test_full_exam_flow_keeps_chat_clean_and_report(test_db, mock_callback, mock_message):
    state = AsyncMock()

    async def fake_generate(scenario, difficulty="medium", weak_areas=None, case_type="open", avoid=None):
        return _choice() if case_type == "choice" else _open()

    evaluation = {
        "score": 8,
        "feedback": "Ответ по делу",
        "strengths": ["структура"],
        "weaknesses": ["мало цифр"],
        "sources": [],
    }

    with patch.object(examiner, "generate_case", side_effect=fake_generate), \
            patch.object(examiner, "get_weak_areas", lambda *a, **k: []), \
            patch.object(examiner, "record_error", lambda *a, **kw: None), \
            patch.object(examiner, "evaluate_answer", AsyncMock(return_value=evaluation)), \
            patch("bot.core.ai_engine.clear_history", new_callable=AsyncMock):
        # 1. старт: три задания, первое — открытый вопрос
        mock_callback.data = "cases_3"
        await examiner.cb_start_exam(mock_callback, state)
        session = examiner.exam_sessions[UID]
        assert [c["type"] for c in session["cases"]] == ["open", "choice", "open"]
        session["case_msg_id"] = 1001  # у мока message_id не число — фиксируем руками
        assert t("exam_task", "ru", n=1, total=3) in _texts(mock_callback.message)[-1]

        # 2. ответ текстом: разбор с кнопкой «Следующее задание», задание убрано из чата
        mock_message.text = "мой ответ"
        await examiner.handle_exam_answer(mock_message, state)
        assert (UID, 1001) in _deleted(mock_message)
        assert t("exam_score", "ru", n=8) in _texts(mock_message)[-1]
        assert _kb(mock_message).inline_keyboard[0][0].callback_data == "next_case"
        # индекс задания не двигается, пока не нажата кнопка
        assert examiner.exam_sessions[UID]["current"] == 0

        # повторный текст на то же задание не оценивается второй раз
        mock_message.answer.reset_mock()
        await examiner.handle_exam_answer(mock_message, state)
        assert t("exam_already_answered", "ru") == _texts(mock_message)[-1]
        assert len(examiner.exam_sessions[UID]["scores"]) == 1

        examiner.exam_sessions[UID]["feedback_msg_id"] = 2001

        # 3. следующее задание: прошлый разбор уходит из чата, задание уже убрано на шаге ответа
        mock_callback.data = "next_case"
        mock_callback.message.answer.reset_mock()
        await examiner.cb_next_case(mock_callback, state)
        session = examiner.exam_sessions[UID]
        assert session["current"] == 1
        assert (UID, 2001) in _deleted(mock_callback)
        session["case_msg_id"] = 1002

        task_text = _texts(mock_callback.message)[-1]
        # варианты идут каждый на своей строке
        assert "\nA) 420 рублей" in task_text
        assert "\nB) 360 рублей" in task_text
        assert "\nC) 240 рублей" in task_text
        assert "\nD) 180 рублей" in task_text
        kb = _kb(mock_callback.message)
        assert [b.text for row in kb.inline_keyboard for b in row] == ["A", "B", "C", "D"]

        # 4. отвечаем на тест: видно и верный вариант, и выбранный неверный
        mock_callback.data = "answer_choice_1"
        mock_callback.message.answer.reset_mock()
        await examiner.cb_answer_choice(mock_callback, state)
        marked = mock_callback.message.edit_text.await_args.args[0]
        assert "\nA) ▫️ 420 рублей" in marked
        assert "\nB) ❌ 360 рублей" in marked
        assert "\nC) ✅ 240 рублей" in marked
        assert _kb(mock_callback.message).inline_keyboard[0][0].callback_data == "next_case"
        examiner.exam_sessions[UID]["feedback_msg_id"] = 2002

        # 5. третье задание — открытый вопрос
        mock_callback.data = "next_case"
        mock_callback.message.answer.reset_mock()
        await examiner.cb_next_case(mock_callback, state)
        session = examiner.exam_sessions[UID]
        assert session["current"] == 2
        deleted = _deleted(mock_callback)
        assert (UID, 1002) in deleted
        assert (UID, 2002) in deleted
        session["case_msg_id"] = 1003
        assert "A) 420 рублей" not in _texts(mock_callback.message)[-1]

        # 6. последнее задание: сначала разбор ответа, итог — по кнопке «Завершить»
        mock_message.text = "последний ответ"
        mock_message.answer.reset_mock()
        await examiner.handle_exam_answer(mock_message, state)
        assert UID in examiner.exam_sessions  # отчёт ещё не отправлен
        assert t("exam_score", "ru", n=8) in _texts(mock_message)[-1]
        kb = _kb(mock_message)
        assert kb.inline_keyboard[0][0].callback_data == "show_results"
        assert kb.inline_keyboard[0][0].text == t("exam_finish", "ru")

        # 7. итоговый отчёт по кнопке
        mock_callback.message.answer.reset_mock()
        await examiner.cb_show_results(mock_callback, state)
        assert UID not in examiner.exam_sessions
        assert t("exam_complete", "ru") in _texts(mock_callback.message)[-1]
        kb = _kb(mock_callback.message)
        assert kb.inline_keyboard[-1][0].callback_data == "back_to_menu_keep"

    # 8. выход в меню отчёт не удаляет: к разбору и pdf можно вернуться в чате
    from bot.handlers.start import cb_back_to_menu_keep

    mock_callback.data = "back_to_menu_keep"
    mock_callback.message.delete.reset_mock()
    mock_callback.message.answer.reset_mock()
    await cb_back_to_menu_keep(mock_callback, state)

    mock_callback.message.delete.assert_not_awaited()
    assert _texts(mock_callback.message)  # меню приходит новым сообщением


def _session(cases, session_id, current=0, case_msg_id=1001, feedback_msg_id=None,
             answers=None, scores=None, total=None):
    return {
        "scenario": "job",
        "cases": cases,
        "current": current,
        "total": total if total is not None else len(cases),
        "session_id": session_id,
        "answers": answers or [],
        "scores": scores or [],
        "timestamp": 9e9,
        "chat_id": UID,
        "case_msg_id": case_msg_id,
        "feedback_msg_id": feedback_msg_id,
    }


@pytest.mark.asyncio
async def test_finish_without_any_answer_is_blocked(test_db, mock_callback):
    # живая кнопка «Завершить» из прошлого экзамена не должна закрывать новый с нулём ответов
    from bot.database.db import create_session, get_or_create_user, get_user_stats

    await get_or_create_user(UID)
    session_id = await create_session(UID, "job", "examiner", 3)
    examiner.exam_sessions[UID] = _session([_open(), _choice(), _open()], session_id)
    mock_callback.data = "show_results"

    try:
        await examiner.cb_show_results(mock_callback, AsyncMock())

        assert UID in examiner.exam_sessions  # экзамен не закрыт
        assert not _texts(mock_callback.message)  # отчёта нет
        mock_callback.answer.assert_awaited_with(t("exam_need_answer", "ru"), show_alert=True)
        stats = await get_user_stats(UID)
        assert stats["scenarios"] == {}  # пустой экзамен в прогресс не попал
    finally:
        examiner.exam_sessions.pop(UID, None)


@pytest.mark.asyncio
async def test_last_review_button_dies_after_report(test_db, mock_callback, mock_message):
    # после отчёта кнопка «Завершить» из разбора последнего задания больше не работает
    from bot.database.db import create_session, get_or_create_user

    await get_or_create_user(UID)
    session_id = await create_session(UID, "job", "examiner", 1)
    examiner.exam_sessions[UID] = _session([_open()], session_id, feedback_msg_id=2001)
    mock_message.text = "ответ"
    evaluation = {"score": 9, "feedback": "хорошо", "strengths": [], "weaknesses": [], "sources": []}

    try:
        with patch.object(examiner, "evaluate_answer", AsyncMock(return_value=evaluation)), \
                patch.object(examiner, "record_error", lambda *a, **kw: None):
            await examiner.handle_exam_answer(mock_message, AsyncMock())
            review_id = examiner.exam_sessions[UID]["feedback_msg_id"]
            await examiner.cb_show_results(mock_callback, AsyncMock())

        assert UID not in examiner.exam_sessions
        # с разбора последнего задания кнопку сняли: нажать её ещё раз не выйдет
        calls = mock_callback.message.bot.edit_message_reply_markup.await_args_list
        assert calls
        assert calls[-1].kwargs["reply_markup"] is None
        assert calls[-1].kwargs["message_id"] == review_id
    finally:
        examiner.exam_sessions.pop(UID, None)


@pytest.mark.asyncio
async def test_abandon_exam_removes_task_and_review(test_db, mock_callback):
    # выход в меню: задание и разбор убираем — кнопки брошенного экзамена не доживают до нового
    from bot.database.db import create_session, get_or_create_user

    await get_or_create_user(UID)
    session_id = await create_session(UID, "job", "examiner", 3)
    examiner.exam_sessions[UID] = _session(
        [_open()], session_id, case_msg_id=1001, feedback_msg_id=2001,
    )

    await examiner.abandon_exam(UID, mock_callback.bot)

    assert UID not in examiner.exam_sessions
    deleted = _deleted(mock_callback)
    assert (UID, 1001) in deleted
    assert (UID, 2001) in deleted


@pytest.mark.asyncio
async def test_finished_exam_is_saved_to_db(test_db, mock_callback, mock_message):
    # честно отвеченное задание попадает и в прогресс, и в pdf-отчёт
    from bot.database.db import get_case_answers, get_user_stats

    async def fake_generate(scenario, difficulty="medium", weak_areas=None, case_type="open", avoid=None):
        return _open()

    evaluation = {"score": 8, "feedback": "ок", "strengths": [], "weaknesses": [], "sources": []}

    with patch.object(examiner, "generate_case", side_effect=fake_generate), \
            patch.object(examiner, "get_weak_areas", lambda *a, **k: []), \
            patch.object(examiner, "record_error", lambda *a, **kw: None), \
            patch.object(examiner, "evaluate_answer", AsyncMock(return_value=evaluation)), \
            patch("bot.core.ai_engine.clear_history", new_callable=AsyncMock):
        mock_callback.data = "cases_3"
        await examiner.cb_start_exam(mock_callback, AsyncMock())
        scenario = examiner.exam_sessions[UID]["scenario"]

        mock_message.text = "развёрнутый ответ"
        await examiner.handle_exam_answer(mock_message, AsyncMock())
        await examiner.cb_show_results(mock_callback, AsyncMock())

    stats = await get_user_stats(UID)
    assert stats["scenarios"][scenario]["sessions"] == 1
    assert stats["scenarios"][scenario]["avg_score"] == 8.0

    answers = await get_case_answers(UID, scenario, only_completed=True)
    assert len(answers) == 1
    assert answers[0]["score"] == 8

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import Message, InlineKeyboardMarkup


@pytest.mark.asyncio
async def test_format_mistakes_translated_to_english():
    """Типовые ошибки переводятся на язык юзера"""
    from bot.handlers.examiner import _format_mistakes

    mistakes = [
        {"error": "Признаваться в незнании", "advice": "Скажи лучше так", "source": "hh.ru"},
    ]
    with patch("bot.handlers.examiner._translate_if_needed", new_callable=AsyncMock) as tr:
        tr.side_effect = lambda text, lang: f"[EN]{text}"
        block = await _format_mistakes(mistakes, "en")

    assert "[EN]Признаваться в незнании" in block
    assert "[EN]Скажи лучше так" in block


@pytest.mark.asyncio
async def test_format_mistakes_empty():
    from bot.handlers.examiner import _format_mistakes
    assert await _format_mistakes([], "ru") == ""


@pytest.mark.asyncio
async def test_back_to_menu_breaks_session(test_db, mock_callback):
    # выход в меню обрывает сессию: состояние и память диалога чистятся
    from bot.core import ai_engine
    from bot.handlers.start import cb_back_to_menu

    uid = mock_callback.from_user.id
    await ai_engine.save_turn(uid, "вопрос", "ответ")
    state = AsyncMock()

    await cb_back_to_menu(mock_callback, state)

    state.clear.assert_awaited_once()
    assert await ai_engine.has_history(uid) is False
    await ai_engine.clear_history(uid)


@pytest.mark.asyncio
async def test_back_to_menu_closes_unfinished_exam(test_db, mock_callback):
    # вышел из экзамена не до конца — сессия закрывается с реальными цифрами
    from bot.database.db import create_session, get_or_create_user
    from bot.handlers import examiner
    from bot.handlers.start import cb_back_to_menu

    uid = mock_callback.from_user.id
    await get_or_create_user(uid)
    session_id = await create_session(uid, "job", "examiner", 5)
    examiner.exam_sessions[uid] = {
        "scenario": "job",
        "cases": [],
        "current": 1,
        "total": 5,
        "session_id": session_id,
        "answers": [],
        "scores": [4, 8],
        "timestamp": 9e9,
    }

    try:
        await cb_back_to_menu(mock_callback, AsyncMock())

        cursor = await test_db.execute(
            "SELECT cases_completed, avg_score, ended_at FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["cases_completed"] == 2
        assert abs(row["avg_score"] - 6.0) < 0.01
        assert row["ended_at"] is not None
        assert uid not in examiner.exam_sessions
    finally:
        examiner.exam_sessions.pop(uid, None)


@pytest.mark.asyncio
async def test_abandon_exam_without_session_is_noop():
    from bot.handlers.examiner import abandon_exam
    await abandon_exam(123456789)
    assert 123456789 not in __import__("bot.handlers.examiner", fromlist=["x"]).exam_sessions


@pytest.mark.asyncio
async def test_answer_choice_marks_case_message(test_db, mock_callback):
    # после ответа на тест задание остаётся в чате, но варианты помечены
    from bot.database.db import create_session, get_or_create_user
    from bot.handlers import examiner

    uid = mock_callback.from_user.id
    await get_or_create_user(uid)
    session_id = await create_session(uid, "job", "examiner", 3)

    case = {
        "type": "choice",
        "situation": "s",
        "question": "q",
        "options": ["A", "B", "C", "D"],
        "correct": 0,
        "explanation": "e",
    }
    examiner.exam_sessions[uid] = {
        "scenario": "job",
        "cases": [case, case, case],
        "current": 0,
        "total": 3,
        "session_id": session_id,
        "answers": [],
        "scores": [],
        "timestamp": 9e9,
        "chat_id": 555,
        "case_msg_id": 777,
        "feedback_msg_id": None,
    }
    mock_callback.data = "answer_choice_2"

    try:
        with patch.object(examiner, "record_error", lambda *a, **kw: None):
            await examiner.cb_answer_choice(mock_callback, AsyncMock())

        # задание не удаляем — размечаем выбранный и верный вариант прямо в нём
        mock_callback.bot.delete_message.assert_not_awaited()
        assert mock_callback.message.edit_text.await_count == 1
        marked = mock_callback.message.edit_text.await_args.args[0]
        assert "✅ A" in marked
        assert "❌ C" in marked
        mock_callback.message.edit_reply_markup.assert_awaited_once_with(reply_markup=None)
        assert examiner.exam_sessions[uid]["case_msg_id"] is None
        # разбор с оценкой — отдельным сообщением
        assert mock_callback.message.answer.await_count == 1
    finally:
        examiner.exam_sessions.pop(uid, None)


@pytest.mark.asyncio
async def test_answer_choice_double_click_ignored(test_db, mock_callback):
    # повторный клик по вариантам не должен второй раз засчитывать ответ
    from bot.database.db import create_session, get_or_create_user
    from bot.handlers import examiner

    uid = mock_callback.from_user.id
    await get_or_create_user(uid)
    session_id = await create_session(uid, "job", "examiner", 3)

    case = {
        "type": "choice",
        "situation": "s",
        "question": "q",
        "options": ["A", "B", "C", "D"],
        "correct": 0,
        "explanation": "e",
    }
    examiner.exam_sessions[uid] = {
        "scenario": "job",
        "cases": [case, case, case],
        "current": 0,
        "total": 3,
        "session_id": session_id,
        "answers": [{"case_idx": 0, "user_answer": "[Выбор: A]", "evaluation": {"score": 10}}],
        "scores": [10],
        "timestamp": 9e9,
        "chat_id": 555,
        "case_msg_id": None,
        "feedback_msg_id": None,
    }
    mock_callback.data = "answer_choice_1"

    try:
        with patch.object(examiner, "record_error") as rec:
            await examiner.cb_answer_choice(mock_callback, AsyncMock())

        assert examiner.exam_sessions[uid]["scores"] == [10]
        assert len(examiner.exam_sessions[uid]["answers"]) == 1
        mock_callback.message.answer.assert_not_awaited()
        rec.assert_not_called()
    finally:
        examiner.exam_sessions.pop(uid, None)


@pytest.mark.asyncio
async def test_next_case_deletes_unanswered_task(test_db, mock_callback):
    # перешли к следующему заданию без ответа — старое задание удаляется
    from bot.database.db import create_session, get_or_create_user
    from bot.handlers import examiner

    uid = mock_callback.from_user.id
    await get_or_create_user(uid)
    session_id = await create_session(uid, "job", "examiner", 3)

    case = {
        "type": "open",
        "situation": "s",
        "question": "q",
        "good_answer_points": [],
        "common_mistakes": [],
    }
    examiner.exam_sessions[uid] = {
        "scenario": "job",
        "cases": [case, case, case],
        "current": 0,
        "total": 3,
        "session_id": session_id,
        "answers": [],
        "scores": [],
        "timestamp": 9e9,
        "chat_id": 555,
        "case_msg_id": 888,
        "feedback_msg_id": 999,
    }
    mock_callback.data = "next_case"

    try:
        await examiner.cb_next_case(mock_callback, AsyncMock())

        mock_callback.bot.delete_message.assert_awaited_once_with(555, 888)
        session = examiner.exam_sessions[uid]
        assert session["current"] == 1
        # новое задание получило свой id
        assert session["case_msg_id"] is not None
        # разбор прошлого задания не удаляли
        assert session["feedback_msg_id"] == 999
    finally:
        examiner.exam_sessions.pop(uid, None)


@pytest.mark.asyncio
async def test_show_screen_always_sends_new_message(mock_message):
    """_show_screen всегда шлёт новое сообщение вниз, а не правит старое"""
    from bot.handlers.start import _show_screen

    mock_message.answer = AsyncMock(return_value=MagicMock(message_id=999))

    await _show_screen(mock_message, "Test text", parse_mode="HTML")

    mock_message.answer.assert_awaited_once()
    mock_message.bot.edit_message_text.assert_not_called()


@pytest.mark.asyncio
async def test_replace_card_sends_new_and_deletes_old(mock_message):
    """_replace_card отправляет новую карточку и удаляет старую"""
    from bot.handlers.start import _replace_card

    mock_message.answer = AsyncMock(return_value=MagicMock(message_id=1000))
    mock_message.delete = AsyncMock()

    await _replace_card(mock_message, "Новая карточка")

    mock_message.answer.assert_awaited_once()
    mock_message.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_replace_card_survives_delete_failure(mock_message):
    """Если старую карточку удалить не вышло — новую всё равно показываем"""
    from bot.handlers.start import _replace_card

    mock_message.answer = AsyncMock(return_value=MagicMock(message_id=1001))
    mock_message.delete = AsyncMock(side_effect=Exception("message to delete not found"))

    await _replace_card(mock_message, "Новая карточка")

    mock_message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_cmd_start_creates_user(test_db, mock_message):
    """Команда /start создаёт пользователя"""
    from bot.handlers.start import cmd_start

    mock_message.text = "/start"
    await cmd_start(mock_message)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args
    assert "Привет" in call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_help(test_db, mock_message):
    """Команда /help показывает справку"""
    from bot.handlers.start import cmd_help

    mock_message.text = "/help"
    await cmd_help(mock_message)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args
    assert "О боте" in call_args[0][0] or "AI-наставник" in call_args[0][0]


@pytest.mark.asyncio
async def test_btn_university(test_db, mock_message):
    """Кнопка 'Выбор вуза'"""
    from bot.handlers.start import btn_university

    mock_message.text = "🎓 Выбор вуза"
    await btn_university(mock_message, AsyncMock())

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args
    assert "вуз" in call_args[0][0].lower()


@pytest.mark.asyncio
async def test_btn_job(test_db, mock_message):
    """Кнопка 'Поиск работы'"""
    from bot.handlers.start import btn_job

    mock_message.text = "💼 Поиск работы"
    await btn_job(mock_message, AsyncMock())

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args
    assert "работ" in call_args[0][0].lower()


@pytest.mark.asyncio
async def test_btn_adaptation(test_db, mock_message):
    """Кнопка 'Адаптация в компании'"""
    from bot.handlers.start import btn_adaptation

    mock_message.text = "🤝 Адаптация в компании"
    await btn_adaptation(mock_message, AsyncMock())

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args
    assert "адаптац" in call_args[0][0].lower()


@pytest.mark.asyncio
async def test_fallback_handler(test_db, mock_message):
    """Fallback handler для неизвестных сообщений — реальный вызов AI замокан"""
    from bot.handlers.start import fallback_handler

    mock_message.text = "как дела?"
    with patch("bot.core.scenarios.answer_info_question", new_callable=AsyncMock) as ai_mock:
        ai_mock.return_value = "Норм. А ты как — резюме уже в порядке?"
        await fallback_handler(mock_message)

    ai_mock.assert_awaited_once()
    assert ai_mock.await_args.args[0] == "как дела?"
    mock_message.answer.assert_called_once_with(
        "Норм. А ты как — резюме уже в порядке?", parse_mode="HTML"
    )

    cursor = await test_db.execute(
        "SELECT COUNT(*) FROM users WHERE user_id = ?", (123456789,)
    )
    row = await cursor.fetchone()
    assert row[0] == 1


@pytest.mark.asyncio
async def test_settings_voice_toggle(test_db, mock_callback):
    """Переключение голоса в настройках"""
    from bot.handlers.start import cb_settings_voice

    await cb_settings_voice(mock_callback)

    mock_callback.answer.assert_called_once()
    call_args = mock_callback.answer.call_args
    assert "Голос" in call_args[0][0]


@pytest.mark.asyncio
async def test_exam_start_requires_scenario(test_db, mock_callback):
    """Экзамен: валидный count создаёт сессию, генерирует кейсы, ставит состояние"""
    from bot.handlers import examiner
    from bot.handlers.examiner import ExamState, cb_start_exam

    user_id = 123456789
    mock_callback.data = "cases_5"
    state = AsyncMock(spec=FSMContext)
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()

    case = {
        "type": "open",
        "situation": "Ситуация",
        "question": "Вопрос?",
        "hint": "Подсказка",
        "good_answer_points": ["пункт"],
        "common_mistakes": [],
    }
    fake_generate = AsyncMock(return_value=case)

    try:
        with patch.object(examiner, "generate_case", fake_generate):
            await cb_start_exam(mock_callback, state)

        session = examiner.exam_sessions.get(user_id)
        assert session is not None
        assert session["total"] == 5
        assert len(session["cases"]) == 5
        # ai здесь всегда отдаёт открытый кейс: невалидные тесты заменяются открытыми,
        # поэтому вызовов больше, чем заданий
        assert fake_generate.await_count >= 5
        assert all(c["type"] == "open" for c in session["cases"])

        state.set_state.assert_awaited_once_with(ExamState.waiting_for_answer)
        mock_callback.answer.assert_awaited_once()
        # карточка больше не правится на месте, а уходит новым сообщением вниз
        mock_callback.message.edit_text.assert_not_awaited()

        calls = mock_callback.message.answer.await_args_list
        assert len(calls) == 2
        # первым уходит карточка «начинаем», вторым — само задание
        assert "5" in calls[0].args[0]
        assert "Задание 1 из 5" in calls[1].args[0]

        cursor = await test_db.execute(
            "SELECT mode, cases_total FROM sessions WHERE user_id = ?", (user_id,)
        )
        rows = await cursor.fetchall()
        assert rows, "session row not created"
        assert rows[0]["mode"] == "examiner"
        assert rows[0]["cases_total"] == 5
    finally:
        examiner.exam_sessions.pop(user_id, None)


@pytest.mark.asyncio
async def test_exam_invalid_count(test_db, mock_callback):
    """Экзамен — неверное количество заданий"""
    from bot.handlers.examiner import cb_start_exam

    mock_callback.data = "cases_7"
    state = AsyncMock(spec=FSMContext)
    state.get_state = AsyncMock(return_value=None)

    await cb_start_exam(mock_callback, state)

    mock_callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_info_question(test_db, mock_message):
    """Информационный вопрос — уходит в answer_info_question, ответ доставляется"""
    from bot.handlers.start import fallback_handler

    mock_message.text = "Какие документы нужны для поступления?"
    with patch("bot.core.scenarios.answer_info_question", new_callable=AsyncMock) as ai_mock:
        ai_mock.return_value = "Паспорт, аттестат и результаты ЕГЭ."
        await fallback_handler(mock_message)

    ai_mock.assert_awaited_once()
    assert "документы" in ai_mock.await_args.args[0].lower()
    sent = mock_message.answer.await_args.args[0]
    assert isinstance(sent, str)
    assert sent == "Паспорт, аттестат и результаты ЕГЭ."

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State


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
    await btn_university(mock_message)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args
    assert "вуз" in call_args[0][0].lower()


@pytest.mark.asyncio
async def test_btn_job(test_db, mock_message):
    """Кнопка 'Поиск работы'"""
    from bot.handlers.start import btn_job

    mock_message.text = "💼 Поиск работы"
    await btn_job(mock_message)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args
    assert "работ" in call_args[0][0].lower()


@pytest.mark.asyncio
async def test_btn_adaptation(test_db, mock_message):
    """Кнопка 'Адаптация в компании'"""
    from bot.handlers.start import btn_adaptation

    mock_message.text = "🤝 Адаптация в компании"
    await btn_adaptation(mock_message)

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
        assert fake_generate.await_count == 5

        state.set_state.assert_awaited_once_with(ExamState.waiting_for_answer)
        mock_callback.answer.assert_awaited_once()
        mock_callback.message.edit_text.assert_awaited_once()
        assert "5" in mock_callback.message.edit_text.await_args.args[0]

        answer_text = mock_callback.message.answer.await_args.args[0]
        assert "Задание 1 из 5" in answer_text

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

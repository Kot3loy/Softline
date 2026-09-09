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
    """Fallback handler для неизвестных сообщений"""
    from bot.handlers.start import fallback_handler

    mock_message.text = "как дела?"
    await fallback_handler(mock_message)

    mock_message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_settings_voice_toggle(test_db, mock_callback):
    """Переключение голоса в настройках"""
    from bot.handlers.start import cb_settings_voice

    await cb_settings_voice(mock_callback)

    mock_callback.answer.assert_called_once()
    call_args = mock_callback.answer.call_args
    assert "Голос" in call_args[0][0]


@pytest.mark.asyncio
async def test_admin_panel_access_denied(test_db, mock_message):
    """Админ-панель без доступа"""
    from bot.handlers.admin import cmd_admin

    mock_message.text = "/admin"
    state = AsyncMock(spec=FSMContext)
    state.get_state = AsyncMock(return_value=None)
    state.clear = AsyncMock()

    await cmd_admin(mock_message, state)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args
    assert "нет доступа" in call_args[0][0].lower()


@pytest.mark.asyncio
async def test_exam_start_requires_scenario(test_db, mock_callback):
    """Экзамен — кол-во заданий валидируется"""
    from bot.handlers.examiner import cb_start_exam

    mock_callback.data = "cases_5"
    state = AsyncMock(spec=FSMContext)
    state.get_state = AsyncMock(return_value=None)
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()

    await cb_start_exam(mock_callback, state)

    # Должен либо отправить задание, либо показать ошибку
    assert mock_callback.answer.call_count > 0 or mock_callback.message.answer.call_count > 0


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
    """Информационный вопрос"""
    from bot.handlers.start import fallback_handler

    mock_message.text = "Какие документы нужны для поступления?"
    await fallback_handler(mock_message)

    mock_message.answer.assert_called_once()

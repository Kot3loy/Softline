"""Проверки, что текст задания удаляется из чата после ответа
и при переходе к следующему заданию."""

import pytest
from unittest.mock import AsyncMock

from bot.handlers import examiner


@pytest.mark.asyncio
async def test_drop_message_survives_telegram_error():
    # сообщение могли удалить руками — падать не должны
    bot = AsyncMock()
    bot.delete_message = AsyncMock(side_effect=Exception("message to delete not found"))

    await examiner._drop_message(bot, 1, 55)

    bot.delete_message.assert_awaited_once_with(1, 55)


@pytest.mark.asyncio
async def test_drop_message_noop_without_id():
    bot = AsyncMock()
    await examiner._drop_message(bot, 1, None)
    await examiner._drop_message(bot, None, 55)
    bot.delete_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_drop_case_clears_stored_id():
    bot = AsyncMock()
    session = {"chat_id": 42, "case_msg_id": 100, "feedback_msg_id": 200}

    await examiner._drop_case(session, bot)

    bot.delete_message.assert_awaited_once_with(42, 100)
    assert session["case_msg_id"] is None
    # разбор не трогаем
    assert session["feedback_msg_id"] == 200


@pytest.mark.asyncio
async def test_drop_case_twice_deletes_once():
    bot = AsyncMock()
    session = {"chat_id": 42, "case_msg_id": 100, "feedback_msg_id": None}

    await examiner._drop_case(session, bot)
    await examiner._drop_case(session, bot)

    assert bot.delete_message.await_count == 1

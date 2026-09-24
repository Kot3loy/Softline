"""Тесты bot/main.py — health handler, on_error, безопасный импорт."""

import json
from datetime import datetime, timezone

import pytest
from aiogram.types import Chat, ErrorEvent, Message, Update, User


@pytest.mark.asyncio
async def test_health_handler_returns_ok():
    from bot.main import health_handler

    resp = await health_handler(None)

    assert resp.status == 200
    assert json.loads(resp.body) == {"status": "ok"}


@pytest.mark.asyncio
async def test_on_error_no_message_no_raise():
    from bot.main import on_error

    event = ErrorEvent(update=Update(update_id=1), exception=RuntimeError("boom"))

    assert await on_error(event) is None


@pytest.mark.asyncio
async def test_on_error_with_message_no_raise(test_db):
    from bot.main import on_error

    msg = Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=Chat(id=1, type="private"),
        from_user=User(id=999888777, is_bot=False, first_name="Err"),
        text="boom",
    )
    event = ErrorEvent(
        update=Update(update_id=2, message=msg),
        exception=ValueError("handler failed"),
    )

    assert await on_error(event) is None

    cursor = await test_db.execute(
        "SELECT COUNT(*) FROM users WHERE user_id = ?", (999888777,)
    )
    row = await cursor.fetchone()
    assert row[0] == 1


def test_import_main_has_no_side_effect_start():
    import bot.main as m

    assert m.bot is None
    assert m.dp is None
    assert not m.shutdown_event.is_set()
    assert callable(m.main)

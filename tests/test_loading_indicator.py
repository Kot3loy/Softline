"""Индикатор загрузки экзаменатора: стикер из пака, удаление после, фолбэк."""

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from bot.utils import loading


@pytest.fixture(autouse=True)
def _reset_loading_cache(monkeypatch):
    loading.reset_cache()
    monkeypatch.setattr(loading, "MIN_SHOW_SECONDS", 0, raising=False)
    yield
    loading.reset_cache()


def _bot_with_stickers(emojis=("🙂", "😐", "😎")):
    bot = AsyncMock()
    stickers = [SimpleNamespace(emoji=e, file_id=f"file_{i}") for i, e in enumerate(emojis)]
    bot.get_sticker_set = AsyncMock(return_value=SimpleNamespace(stickers=stickers))
    bot.send_sticker = AsyncMock(return_value=SimpleNamespace(message_id=42))
    bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=43))
    bot.delete_message = AsyncMock()
    return bot


@pytest.mark.asyncio
async def test_no_pack_configured_uses_text_fallback(monkeypatch):
    monkeypatch.setattr("bot.utils.loading.config.LOADING_STICKER_PACK", "", raising=False)
    bot = _bot_with_stickers()

    async with loading.LoadingIndicator(bot, 100, fallback_text="⏳ Подбираю задания…"):
        pass

    bot.send_sticker.assert_not_awaited()
    bot.send_message.assert_awaited_once_with(100, "⏳ Подбираю задания…")
    bot.delete_message.assert_awaited_once_with(100, 43)


@pytest.mark.asyncio
async def test_sticker_found_by_emoji_and_deleted(monkeypatch):
    monkeypatch.setattr("bot.utils.loading.config.LOADING_STICKER_PACK", "my_pack", raising=False)
    monkeypatch.setattr("bot.utils.loading.config.LOADING_STICKER_EMOJI", "😐", raising=False)
    bot = _bot_with_stickers()

    async with loading.LoadingIndicator(bot, 100, fallback_text="⏳"):
        pass

    bot.get_sticker_set.assert_awaited_once_with(name="my_pack")
    bot.send_sticker.assert_awaited_once_with(100, "file_1")
    bot.delete_message.assert_awaited_once_with(100, 42)
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_sticker_file_id_is_cached(monkeypatch):
    monkeypatch.setattr("bot.utils.loading.config.LOADING_STICKER_PACK", "my_pack", raising=False)
    monkeypatch.setattr("bot.utils.loading.config.LOADING_STICKER_EMOJI", "😐", raising=False)
    bot = _bot_with_stickers()

    async with loading.LoadingIndicator(bot, 100, fallback_text=""):
        pass
    async with loading.LoadingIndicator(bot, 100, fallback_text=""):
        pass

    # пак запрашиваем один раз, второй раз берём file_id из кэша
    bot.get_sticker_set.assert_awaited_once()


@pytest.mark.asyncio
async def test_unknown_emoji_falls_back_to_second_sticker(monkeypatch):
    monkeypatch.setattr("bot.utils.loading.config.LOADING_STICKER_PACK", "my_pack", raising=False)
    monkeypatch.setattr("bot.utils.loading.config.LOADING_STICKER_EMOJI", "🚀", raising=False)
    bot = _bot_with_stickers()

    async with loading.LoadingIndicator(bot, 100, fallback_text=""):
        pass

    bot.send_sticker.assert_awaited_once_with(100, "file_1")


@pytest.mark.asyncio
async def test_sticker_send_error_refetches_once(monkeypatch):
    monkeypatch.setattr("bot.utils.loading.config.LOADING_STICKER_PACK", "my_pack", raising=False)
    monkeypatch.setattr("bot.utils.loading.config.LOADING_STICKER_EMOJI", "😐", raising=False)
    bot = _bot_with_stickers()
    # первый раз file_id «протух» — отправка падает, после перезапроса пака всё ок
    bot.send_sticker = AsyncMock(side_effect=[Exception("wrong file identifier"), SimpleNamespace(message_id=44)])

    async with loading.LoadingIndicator(bot, 100, fallback_text=""):
        pass

    assert bot.get_sticker_set.await_count == 2
    bot.delete_message.assert_awaited_once_with(100, 44)


@pytest.mark.asyncio
async def test_bot_errors_do_not_break_generation(monkeypatch):
    monkeypatch.setattr("bot.utils.loading.config.LOADING_STICKER_PACK", "my_pack", raising=False)
    bot = _bot_with_stickers()
    bot.get_sticker_set = AsyncMock(side_effect=Exception("telegram down"))
    bot.send_message = AsyncMock(side_effect=Exception("also down"))

    # даже если индикатор не показался, экзамен должен продолжиться
    async with loading.LoadingIndicator(bot, 100, fallback_text="⏳"):
        pass


@pytest.mark.asyncio
async def test_min_show_time_waits(monkeypatch):
    monkeypatch.setattr("bot.utils.loading.config.LOADING_STICKER_PACK", "my_pack", raising=False)
    monkeypatch.setattr(loading, "MIN_SHOW_SECONDS", 5, raising=False)
    bot = _bot_with_stickers()
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(loading.asyncio, "sleep", fake_sleep)

    async with loading.LoadingIndicator(bot, 100, fallback_text=""):
        pass

    # если генерация прошла мгновенно, стикер всё равно держим минимум MIN_SHOW_SECONDS
    assert sleeps and sleeps[0] > 0

# индикатор загрузки: пока ai подбирает задания, показываем стикер, потом удаляем
# стикер лучше спиннера: анимированный .tgs крутится сам и не даёт flood от edit-запросов

import asyncio
import time
import logging

from bot.config import config

logger = logging.getLogger(__name__)

MIN_SHOW_SECONDS = 1.2

_sticker_file_id: str | None = None


def reset_cache():
    # сбрасываем кэш file_id (нужно тестам и принудительному обновлению)
    global _sticker_file_id
    _sticker_file_id = None


async def _resolve_sticker(bot, refetch: bool = False) -> str | None:
    # file_id стикера ищем по эмодзи; пак задаёт пользователь в .env
    global _sticker_file_id
    if _sticker_file_id and not refetch:
        return _sticker_file_id

    pack = (config.LOADING_STICKER_PACK or "").strip()
    if not pack:
        return None

    try:
        sticker_set = await bot.get_sticker_set(name=pack)
    except Exception as e:
        logger.warning(f"Не удалось загрузить пак стикеров {pack}: {e}")
        return None

    try:
        stickers = list(getattr(sticker_set, "stickers", None) or [])
        if not stickers:
            return None

        emoji = (config.LOADING_STICKER_EMOJI or "").strip()
        chosen = None
        if emoji:
            chosen = next((s for s in stickers if getattr(s, "emoji", None) == emoji), None)
        if chosen is None and len(stickers) > 1:
            # фолбэк: второй стикер пака (первый часто служебный)
            chosen = stickers[1]
        if chosen is None:
            chosen = stickers[0]

        _sticker_file_id = getattr(chosen, "file_id", None)
        return _sticker_file_id
    except Exception as e:
        logger.debug(f"Не удалось выбрать стикер из пака {pack}: {e}")
        return None


class LoadingIndicator:
    # контекстный менеджер: показываем индикатор на входе, убираем на выходе.
    # при любой ошибке телеграма молча продолжаем — экзамен важнее картинки
    def __init__(self, bot, chat_id: int, fallback_text: str = ""):
        self.bot = bot
        self.chat_id = chat_id
        self.fallback_text = fallback_text
        self.message_id = None
        self.started_at = None

    async def __aenter__(self):
        self.started_at = time.monotonic()
        file_id = await _resolve_sticker(self.bot)

        if not file_id:
            if self.fallback_text:
                try:
                    sent = await self.bot.send_message(self.chat_id, self.fallback_text)
                    self.message_id = getattr(sent, "message_id", None)
                except Exception as e:
                    logger.debug(f"Текстовый индикатор не отправился: {e}")
            return self

        try:
            sent = await self.bot.send_sticker(self.chat_id, file_id)
            self.message_id = getattr(sent, "message_id", None)
        except Exception as e:
            # file_id мог устареть — один раз перезапрашиваем пак
            logger.debug(f"Стикер не отправился ({e}) — обновляю пак")
            file_id = await _resolve_sticker(self.bot, refetch=True)
            if file_id:
                try:
                    sent = await self.bot.send_sticker(self.chat_id, file_id)
                    self.message_id = getattr(sent, "message_id", None)
                except Exception as e2:
                    logger.debug(f"Стикер так и не отправился: {e2}")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        # держим индикатор минимум MIN_SHOW_SECONDS, чтобы не мигал на быстрой генерации
        if self.started_at is not None:
            remaining = MIN_SHOW_SECONDS - (time.monotonic() - self.started_at)
            if remaining > 0:
                await asyncio.sleep(remaining)

        if self.message_id:
            try:
                await self.bot.delete_message(self.chat_id, self.message_id)
            except Exception as e:
                logger.debug(f"Индикатор не удалился: {e}")
        self.message_id = None
        return False

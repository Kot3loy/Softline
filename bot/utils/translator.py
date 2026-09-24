"""Модуль перевода — deep-translator (Google Translate, бесплатно)"""

import logging
import asyncio
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

# Кэш для перевода (чтобы не переводить одно и то же)
_translate_cache: dict[str, str] = {}
MAX_CACHE_SIZE = 500


async def translate_text(text: str, target_lang: str, source_lang: str = "auto") -> str:
    """Перевести текст на целевой язык"""
    if not text or not text.strip():
        return text

    if target_lang == "ru":
        return text  # Уже на русском, перевод не нужен

    # Проверяем кэш
    cache_key = f"{hash(text)}_{text[:100]}"
    if cache_key in _translate_cache:
        return _translate_cache[cache_key]

    try:
        translator = GoogleTranslator(source=source_lang, target=target_lang)
        # deep-translator синхронный, оборачиваем в to_thread
        result = await asyncio.to_thread(translator.translate, text)

        if result:
            # Кэшируем
            if len(_translate_cache) < MAX_CACHE_SIZE:
                _translate_cache[cache_key] = result
            return result
    except Exception as e:
        logger.error(f"Ошибка перевода: {e}")

    return text  # Fallback — оригинальный текст

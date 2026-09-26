# переводчик: гугл-транслейт через deep-translator (бесплатно)
# если библиотека не установлена или сеть недоступна — отдаём исходный текст,
# бот при этом не падает

import logging
import asyncio
import re

logger = logging.getLogger(__name__)

# Кэш для перевода (чтобы не переводить одно и то же)
_translate_cache: dict[str, str] = {}
MAX_CACHE_SIZE = 500

# сорт тегов для перевода html, чтобы не потерять <b> и прочее
_TAG_RE = re.compile(r"(<[^>]+>)")

_translator_cls = None
_translator_checked = False


def _get_translator_cls():
    # ленивый импорт: пока переводчик не нужен, библиотека не грузится
    global _translator_cls, _translator_checked
    if _translator_checked:
        return _translator_cls
    _translator_checked = True
    try:
        from deep_translator import GoogleTranslator
        _translator_cls = GoogleTranslator
    except Exception as e:
        logger.warning(f"Переводчик недоступен, отдаю текст как есть: {e}")
        _translator_cls = None
    return _translator_cls


def is_available() -> bool:
    return _get_translator_cls() is not None


async def translate_text(text: str, target_lang: str, source_lang: str = "auto") -> str:
    if not text or not text.strip():
        return text

    if target_lang == "ru":
        return text  # уже на русском, переводить нечего

    cls = _get_translator_cls()
    if cls is None:
        return text

    # проверяю кэш — чтобы не шарить в гугл по каждому слову
    cache_key = f"{hash(text)}_{text[:100]}"
    if cache_key in _translate_cache:
        return _translate_cache[cache_key]

    try:
        translator = cls(source=source_lang, target=target_lang)
        # deep-translator синхронный, поэтому толкаю его в поток
        result = await asyncio.to_thread(translator.translate, text)

        if result:
            if len(_translate_cache) < MAX_CACHE_SIZE:
                _translate_cache[cache_key] = result
            return result
    except Exception as e:
        logger.error(f"Ошибка перевода: {e}")

    return text  # если не вышло — оригинальный текст


async def translate_html(text: str, target_lang: str) -> str:
    # перевожу текст, но html-теги оставляю как есть
    if not text or target_lang == "ru":
        return text

    parts = _TAG_RE.split(text)
    translated = []
    for part in parts:
        if not part or part.startswith("<") and part.endswith(">"):
            translated.append(part)
        else:
            translated.append(await translate_text(part, target_lang))
    return "".join(translated)

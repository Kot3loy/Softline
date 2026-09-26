import asyncio

import pytest

from bot.utils import translator
from bot.utils.translator import translate_html, translate_text


@pytest.fixture(autouse=True)
def clean_cache():
    translator._translate_cache.clear()
    yield
    translator._translate_cache.clear()


def test_translate_skipped_for_russian():
    # на русский переводить нечего, текст возвращается как есть
    assert asyncio.run(translate_text("Привет", "ru")) == "Привет"


@pytest.mark.asyncio
async def test_translate_returns_original_when_translator_missing(monkeypatch):
    # если библиотека не установлена — текст остаётся как есть, без исключения
    monkeypatch.setattr(translator, "_translator_cls", None)
    monkeypatch.setattr(translator, "_translator_checked", True)
    text = "Проверка недоступности переводчика"
    assert await translate_text(text, "en") == text


@pytest.mark.asyncio
async def test_translate_html_keeps_tags(monkeypatch):
    # теги не переводятся и не теряются
    async def fake_translate(text, target_lang, source_lang="auto"):
        return text.upper()

    monkeypatch.setattr(translator, "translate_text", fake_translate)
    result = await translate_html("<b>Сценарий</b>: выбор вуза", "en")
    assert result == "<b>СЦЕНАРИЙ</b>: ВЫБОР ВУЗА"


@pytest.mark.asyncio
async def test_translate_html_russian_passthrough():
    text = "<b>Сценарий</b>: выбор вуза"
    assert await translate_html(text, "ru") == text

"""Inline mode handler — @bot query поиск по базе знаний"""

import html
import logging
import asyncio
from pathlib import Path
from aiogram import Router, F
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from bot.translations import t, STRINGS
from bot.core.rag import search
from bot.database.db import get_or_create_user
from bot.utils.lang import get_lang

router = Router()
logger = logging.getLogger(__name__)


def _truncate(text: str, max_len: int = 50) -> str:
    """Обрезать текст до max_len символов"""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


@router.inline_query()
async def inline_query_handler(inline_query: InlineQuery):
    """Обработка inline query — поиск по базе знаний"""
    query = inline_query.query.strip()
    user_id = inline_query.from_user.id

    # Получаем язык пользователя
    user_data = await get_or_create_user(user_id)
    lang = get_lang(user_data)

    if not query:
        # Пустой запрос — показываем подсказку
        hint = t("inline_hint", lang) if "inline_hint" in STRINGS else (
            "Напиши запрос для поиска по базе знаний..."
        )
        results = [
            InlineQueryResultArticle(
                id="hint",
                title="🔍 " + (t("inline_search", lang) if "inline_search" in STRINGS else "Поиск по базе знаний"),
                description=hint,
                input_message_content=InputTextMessageContent(
                    message_text=hint
                ),
            )
        ]
        await inline_query.answer(results, cache_time=1, is_personal=True)
        return

    # Ищем в базе знаний
    try:
        docs = await asyncio.to_thread(search, query, k=5)
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        docs = []

    if not docs:
        # Ничего не найдено
        not_found = t("inline_not_found", lang) if "inline_not_found" in STRINGS else (
            f"Ничего не найдено по запросу: {query}"
        )
        results = [
            InlineQueryResultArticle(
                id="not_found",
                title="🔍 " + (t("inline_not_found_title", lang) if "inline_not_found_title" in STRINGS else "Ничего не найдено"),
                description=not_found[:100],
                input_message_content=InputTextMessageContent(
                    message_text=not_found
                ),
            )
        ]
        await inline_query.answer(results, cache_time=1, is_personal=True)
        return

    # Формируем результаты
    results = []
    for i, doc in enumerate(docs):
        raw_source = str(doc.metadata.get("source", "Источник"))
        source = Path(raw_source).name
        content = doc.page_content[:200]

        # Определяем тип контента
        if "university" in raw_source.lower() or "вуз" in raw_source.lower():
            emoji = "🎓"
        elif "company" in raw_source.lower() or "компания" in raw_source.lower() or "job" in raw_source.lower():
            emoji = "💼"
        elif "adaptation" in raw_source.lower() or "адаптация" in raw_source.lower():
            emoji = "🤝"
        else:
            emoji = "📄"

        # Создаем кнопку для перехода в инфо-режим
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📖 " + (t("inline_open", lang) if "inline_open" in STRINGS else "Открыть"),
                callback_data=f"info_from_inline_{i}"
            )]
        ])

        results.append(
            InlineQueryResultArticle(
                id=f"doc_{i}",
                title=f"{emoji} {_truncate(source, 40)}",
                description=_truncate(content, 100),
                input_message_content=InputTextMessageContent(
                    message_text=f"{emoji} <b>{html.escape(source)}</b>\n\n{html.escape(content)}...",
                    parse_mode="HTML"
                ),
                reply_markup=keyboard,
            )
        )

    await inline_query.answer(results, cache_time=60, is_personal=True)


@router.callback_query(F.data.startswith("info_from_inline_"))
async def cb_info_from_inline(cb):
    """Обработка нажатия на кнопку 'Открыть' из inline результатов"""
    # TODO: реализовать переход в инфо-режим с контекстом (планируется)
    await cb.answer("🚧 В разработке", show_alert=True)
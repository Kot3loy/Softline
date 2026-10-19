"""Inline-режим: результаты показывают название и ссылку, без имён файлов на диске."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers.inline import inline_query_handler


def _doc(title="Как выбрать вуз", url="https://hh.ru/article/25573"):
    return SimpleNamespace(
        page_content="Текст про выбор вуза и критерии",
        metadata={
            "source": "data/universities/21_profession_and_vuz.md",
            "title": title,
            "source_url": url,
            "source_type": "universities",
        },
    )


def _query(text="вуз"):
    q = AsyncMock()
    q.query = text
    q.from_user = MagicMock()
    q.from_user.id = 777001
    q.answer = AsyncMock()
    return q


@pytest.mark.asyncio
async def test_inline_results_show_human_title_and_url(test_db):
    q = _query()
    with patch("bot.handlers.inline.search", return_value=[_doc()]):
        await inline_query_handler(q)

    results = q.answer.await_args.args[0]
    body = results[0].input_message_content.message_text
    assert "Как выбрать вуз" in body
    assert "https://hh.ru/article/25573" in body
    assert ".md" not in body
    assert "data/" not in body


@pytest.mark.asyncio
async def test_inline_title_has_no_file_extension(test_db):
    q = _query()
    with patch("bot.handlers.inline.search", return_value=[_doc()]):
        await inline_query_handler(q)

    results = q.answer.await_args.args[0]
    assert ".md" not in results[0].title


@pytest.mark.asyncio
async def test_inline_without_url_still_works(test_db):
    q = _query()
    with patch("bot.handlers.inline.search", return_value=[_doc(url=None)]):
        await inline_query_handler(q)

    results = q.answer.await_args.args[0]
    body = results[0].input_message_content.message_text
    assert "Как выбрать вуз" in body
    assert "<a href" not in body

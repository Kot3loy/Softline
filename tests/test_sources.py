"""Тесты источников: человеческий вид, релевантность, отсутствие путей к файлам."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from bot.core import rag
from bot.core.scenarios import answer_info_question, _format_sources, _is_refusal, _SCENARIO_SOURCE_TYPES


def _doc(url, title, source="data/universities/msu.md", source_type="universities"):
    return SimpleNamespace(
        page_content="контент про вуз",
        metadata={"source": source, "title": title, "source_url": url, "source_type": source_type},
    )


# --- rag: человеческое название ---

def test_extract_title_prefers_h1(tmp_path):
    md = tmp_path / "some_file.md"
    content = "---\nscenario: cases\n---\n\n# Как выбрать вуз\n\nтекст"
    assert rag._extract_title(content, md) == "Как выбрать вуз"


def test_extract_title_falls_back_to_filename(tmp_path):
    md = tmp_path / "some_file.md"
    assert rag._extract_title("без заголовка", md) == "some file"


def test_rag_source_metadata_is_relative_path():
    # абсолютный путь содержал бы имя пользователя ПК — храним относительный
    rag._documents = []
    docs = rag.search("как выбрать вуз", 3)
    assert docs
    for doc in docs:
        source = doc.metadata.get("source", "")
        assert not source.startswith(("C:", "/", "\\\\"))
        assert "Users" not in source


# --- форматирование источников ---

def test_format_sources_human_readable_without_paths():
    block = _format_sources([_doc("https://career.hh.ru/article/kak-vybrat-vuz", "Как выбрать вуз")], "ru")
    assert "career.hh.ru" in block
    assert "Как выбрать вуз" in block
    assert "data/" not in block
    assert "C:\\" not in block


def test_format_sources_dedupes_and_limits():
    docs = [_doc(f"https://example.com/{i}", f"T{i}") for i in range(6)] + [_doc("https://example.com/0", "Дубль")]
    block = _format_sources(docs, "ru")
    assert block.count("<a href=") == 3


def test_format_sources_skips_docs_without_url():
    assert _format_sources([_doc(None, "Без ссылки")], "ru") == ""


def test_format_sources_escapes_html():
    block = _format_sources([_doc("https://example.com/a", 'Вуз <b>"X"</b>')], "ru")
    assert "<b>" not in block.replace("<b>Источники</b>", "")
    assert "&lt;b&gt;" in block


# --- релевантность: фильтр по сценарию ---

def test_scenario_source_types_match_menu_scenarios():
    assert set(_SCENARIO_SOURCE_TYPES) == {"university", "job", "adaptation"}
    assert "lead" not in _SCENARIO_SOURCE_TYPES["university"]
    assert "lead" not in _SCENARIO_SOURCE_TYPES["job"]


@pytest.mark.asyncio
async def test_answer_info_question_filters_search_by_scenario(test_db):
    with patch("bot.core.scenarios.search", return_value=[]) as search_mock, \
            patch("bot.core.scenarios.ask_ai", new_callable=AsyncMock) as ai_mock:
        ai_mock.return_value = "ответ"
        await answer_info_question("где учиться", "university")

    assert search_mock.call_args.args[2] == _SCENARIO_SOURCE_TYPES["university"]


# --- отказы не получают источники ---

def test_is_refusal_detects_off_topic_answer():
    assert _is_refusal("Тема выбора вуза не моя специализация. Я помогаю только с адаптацией.")
    assert not _is_refusal("Смотри МИФИ, ВШЭ и ИТМО — сильные программы.")


@pytest.mark.asyncio
async def test_refusal_answer_has_no_sources(test_db):
    docs = [_doc("https://career.hh.ru/article/kak-vybrat-vuz", "Как выбрать вуз")]
    refusal = "Тема выбора вуза не моя специализация. Я помогаю только с адаптацией на новой работе."
    with patch("bot.core.scenarios.search", return_value=docs), \
            patch("bot.core.scenarios.ask_ai", new_callable=AsyncMock) as ai_mock:
        ai_mock.return_value = refusal
        result = await answer_info_question("q", "adaptation")

    assert result == refusal
    assert "http" not in result


@pytest.mark.asyncio
async def test_useful_answer_appends_sources(test_db):
    docs = [_doc("https://career.hh.ru/article/kak-vybrat-vuz", "Как выбрать вуз")]
    answer = "Смотри МИФИ, ВШЭ и ИТМО — там сильная техническая база и много практики для студентов."
    with patch("bot.core.scenarios.search", return_value=docs), \
            patch("bot.core.scenarios.ask_ai", new_callable=AsyncMock) as ai_mock:
        ai_mock.return_value = answer
        result = await answer_info_question("q", "university")

    assert "career.hh.ru" in result
    assert "C:\\" not in result


# --- экзаменатор: реальные ссылки в оценке ---

@pytest.mark.asyncio
async def test_evaluate_answer_returns_real_sources():
    from bot.core import ai_engine
    docs = [_doc("https://hh.ru/article/32647", "Гайд по адаптации", source_type="companies")]
    with patch("bot.core.ai_engine.search", return_value=docs), \
            patch("bot.core.ai_engine.ask_ai", new_callable=AsyncMock) as ai_mock:
        ai_mock.return_value = json.dumps({"score": 7, "feedback": "ок"})
        result = await ai_engine.evaluate_answer("я бы спросил коллегу", {"situation": "s", "question": "q"})

    assert result["sources"] == [{"title": "Гайд по адаптации", "url": "https://hh.ru/article/32647"}]


@pytest.mark.asyncio
async def test_evaluate_answer_has_sources_key_when_rag_empty():
    from bot.core import ai_engine
    with patch("bot.core.ai_engine.search", return_value=[]), \
            patch("bot.core.ai_engine.ask_ai", new_callable=AsyncMock) as ai_mock:
        ai_mock.return_value = json.dumps({"score": 5, "feedback": "ок"})
        result = await ai_engine.evaluate_answer("короткий ответ", {"situation": "s", "question": "q"})

    assert result["sources"] == []


# --- БД: сохранение вопроса и источников ---

@pytest.mark.asyncio
async def test_save_case_answer_stores_question_and_sources(test_db):
    from bot.database.db import create_session, save_case_answer, get_case_answers, get_or_create_user

    await get_or_create_user(424242)
    sid = await create_session(424242, "adaptation", "examiner", 3)
    sources = [{"title": "Гайд", "url": "https://hh.ru/article/32647"}]
    await save_case_answer(
        sid, 424242, "adaptation_1", "adaptation", "мой ответ", 8, "фидбек",
        question="Что делать в первый день?", sources=sources,
    )

    answers = await get_case_answers(424242)
    assert answers
    assert answers[0]["question"] == "Что делать в первый день?"
    assert json.loads(answers[0]["sources"]) == sources

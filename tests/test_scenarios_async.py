"""Async-тесты answer_info_question — контекстный и no-context RAG-пути."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from bot.core import ai_engine
from bot.core.scenarios import answer_info_question, get_welcome_message
from bot.translations import t


@pytest.mark.asyncio
async def test_answer_info_question_with_context():
    doc = SimpleNamespace(
        page_content="МГУ проходной балл 270 по профилю",
        metadata={"source": "data/universities/msu.md"},
    )
    with patch("bot.core.scenarios.search", return_value=[doc]) as search_mock, \
            patch("bot.core.scenarios.ask_ai", new_callable=AsyncMock) as ai_mock:
        ai_mock.return_value = "Ответ, основанный на контексте"
        result = await answer_info_question(
            "какой проходной в МГУ?", "university", user_id=777
        )

    assert result == "Ответ, основанный на контексте"
    search_mock.assert_called_once_with("какой проходной в МГУ?", 3, None)
    assert ai_mock.await_count == 1

    prompt = ai_mock.await_args.args[0]
    assert "МГУ проходной балл 270" in prompt
    assert t("rag_relevant_info", "ru") in prompt
    assert t("rag_use_context", "ru") in prompt

    assert 777 in ai_engine._last_responses
    assert "Ответ, основанный на контексте" in ai_engine._last_responses[777][0]
    ai_engine._last_responses.pop(777, None)
    ai_engine._last_responses_ttl.pop(777, None)


@pytest.mark.asyncio
async def test_answer_info_question_no_context():
    with patch("bot.core.scenarios.search", return_value=[]) as search_mock, \
            patch("bot.core.scenarios.ask_ai", new_callable=AsyncMock) as ai_mock:
        ai_mock.return_value = "Ответ без базы знаний"
        result = await answer_info_question(
            "абракадабра запрос", "job", lang="en"
        )

    assert result == "Ответ без базы знаний"
    search_mock.assert_called_once_with("абракадабра запрос", 3, None)

    prompt = ai_mock.await_args.args[0]
    assert t("rag_no_context", "en") in prompt
    assert t("rag_relevant_info", "en") not in prompt


@pytest.mark.asyncio
async def test_answer_info_question_system_prompt_from_registry():
    with patch("bot.core.scenarios.search", return_value=[]), \
            patch("bot.core.scenarios.ask_ai", new_callable=AsyncMock) as ai_mock:
        ai_mock.return_value = "ok"
        await answer_info_question("q", "adaptation")

    system_prompt = ai_mock.await_args.args[1]
    assert "адаптируться" in system_prompt or "адаптаци" in system_prompt.lower()


@pytest.mark.asyncio
async def test_answer_info_question_saves_history_only_with_user_id():
    with patch("bot.core.scenarios.search", return_value=[]), \
            patch("bot.core.scenarios.ask_ai", new_callable=AsyncMock) as ai_mock:
        ai_mock.return_value = "ответ"
        await answer_info_question("q", "university")

    assert 777 not in ai_engine._last_responses


@pytest.mark.asyncio
async def test_answer_info_question_includes_frame():
    with patch("bot.core.scenarios.search", return_value=[]), \
            patch("bot.core.scenarios.ask_ai", new_callable=AsyncMock) as ai_mock:
        ai_mock.return_value = "ok"
        await answer_info_question("тест вопрос", "job")

    prompt = ai_mock.await_args.args[0]
    assert "Тема: поиск работы, резюме, собеседования, стажировки, карьера" in prompt
    assert "Держись темы" in prompt
    assert "Приветствия — коротко" in prompt


@pytest.mark.asyncio
async def test_welcome_includes_hint_and_examples():
    with patch("bot.core.scenarios._get_prompt") as mock_get_prompt:
        mock_get_prompt.side_effect = lambda key: {
            "welcome_university": "🎓 <b>Выбор вуза</b>\n\nПомогу выбрать вуз.",
            "welcome_university_examples": "<b>Примеры вопросов:</b>\n• Какие проходные баллы на МГУ?",
        }.get(key, "")

        welcome = await get_welcome_message("university")

    assert "Напиши свой вопрос" in welcome
    assert "Примеры вопросов" in welcome
    assert "проходные баллы" in welcome


@pytest.mark.asyncio
async def test_info_ask_hint_translation():
    assert t("info_ask_hint", "ru") == "✍️ Напиши свой вопрос — отвечу по теме."
    assert t("info_ask_hint", "en") == "✍️ Ask your question — I'll answer on topic."

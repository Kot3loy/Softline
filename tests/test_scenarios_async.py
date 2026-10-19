"""Async-тесты answer_info_question — контекстный и no-context RAG-пути."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from bot.core import ai_engine
from bot.core.scenarios import answer_info_question, get_welcome_message
from bot.translations import t


@pytest.mark.asyncio
async def test_answer_info_question_with_context(test_db):
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

    assert 777 in ai_engine._sessions
    assert ai_engine._sessions[777][0]["answer"] == "Ответ, основанный на контексте"
    await ai_engine.clear_history(777)


@pytest.mark.asyncio
async def test_answer_info_question_no_context(test_db):
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

    assert 777 not in ai_engine._sessions


@pytest.mark.asyncio
async def test_answer_info_question_keeps_session_context(test_db):
    # второй вопрос должен видеть первый диалог в промпте
    uid = 888001
    await ai_engine.clear_history(uid)
    try:
        with patch("bot.core.scenarios.search", return_value=[]), \
                patch("bot.core.scenarios.ask_ai", new_callable=AsyncMock) as ai_mock:
            ai_mock.return_value = "Первый ответ"
            await answer_info_question("первый вопрос", "university", user_id=uid)
            first_prompt = ai_mock.await_args.args[0]
            assert "История диалога" not in first_prompt

            ai_mock.reset_mock()
            ai_mock.return_value = "Второй ответ"
            await answer_info_question("второй вопрос", "university", user_id=uid)
            second_prompt = ai_mock.await_args.args[0]

        assert "История диалога" in second_prompt
        assert "первый вопрос" in second_prompt
        assert "Первый ответ" in second_prompt
    finally:
        await ai_engine.clear_history(uid)


@pytest.mark.asyncio
async def test_history_cleared_on_exit(test_db):
    # после выхода из меню память сессии обнуляется
    uid = 888002
    await ai_engine.clear_history(uid)
    with patch("bot.core.scenarios.search", return_value=[]), \
            patch("bot.core.scenarios.ask_ai", new_callable=AsyncMock) as ai_mock:
        ai_mock.return_value = "ответ"
        await answer_info_question("вопрос", "university", user_id=uid)
        assert await ai_engine.has_history(uid) is True

    await ai_engine.clear_history(uid)
    assert await ai_engine.has_history(uid) is False

    with patch("bot.core.scenarios.search", return_value=[]), \
            patch("bot.core.scenarios.ask_ai", new_callable=AsyncMock) as ai_mock:
        ai_mock.return_value = "ответ"
        await answer_info_question("вопрос", "university", user_id=uid)
        assert "История диалога" not in ai_mock.await_args.args[0]


@pytest.mark.asyncio
async def test_history_capped_at_max_turns(test_db):
    uid = 888003
    await ai_engine.clear_history(uid)
    try:
        with patch("bot.core.scenarios.search", return_value=[]), \
                patch("bot.core.scenarios.ask_ai", new_callable=AsyncMock) as ai_mock:
            ai_mock.side_effect = [f"ответ {i}" for i in range(6)]
            for i in range(6):
                await answer_info_question(f"вопрос {i}", "university", user_id=uid)

        assert len(await ai_engine.get_history(uid)) == ai_engine.MAX_TURNS
    finally:
        await ai_engine.clear_history(uid)


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


@pytest.mark.asyncio
async def test_welcome_translated_to_english():
    # тексты из реестра на английском тоже должны быть английскими
    async def fake_translate_html(text, lang):
        assert lang == "en"
        return text.replace("Выбор вуза", "University choice")

    with patch("bot.core.scenarios._get_prompt") as mock_get_prompt, \
            patch("bot.core.scenarios.translate_html", new_callable=AsyncMock, side_effect=fake_translate_html):
        mock_get_prompt.side_effect = lambda key: {
            "welcome_university": "🎓 <b>Выбор вуза</b>\n\nПомогу выбрать вуз.",
            "welcome_university_examples": "<b>Примеры вопросов:</b>\n• Какие проходные баллы на МГУ?",
        }.get(key, "")

        welcome = await get_welcome_message("university", "en")

    assert "University choice" in welcome
    assert "Выбор вуза" not in welcome
    assert "Ask your question" in welcome


@pytest.mark.asyncio
async def test_welcome_russian_not_translated():
    # для русского перевод не дёргаем
    with patch("bot.core.scenarios._get_prompt") as mock_get_prompt, \
            patch("bot.core.scenarios.translate_html", new_callable=AsyncMock) as tr_mock:
        mock_get_prompt.side_effect = lambda key: {
            "welcome_university": "🎓 <b>Выбор вуза</b>",
        }.get(key, "")

        await get_welcome_message("university", "ru")

    tr_mock.assert_not_called()

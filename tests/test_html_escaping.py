"""HTML в ответах LLM не должен ломать сообщения Telegram."""

from unittest.mock import AsyncMock, patch

import pytest

from bot.database.db import create_session, get_or_create_user
from bot.handlers import examiner, info

UID = 987654


@pytest.mark.asyncio
async def test_info_answer_keeps_source_markup(test_db, mock_message):
    """Тело ответа экранировано, а блок источников остаётся HTML-ссылками"""
    mock_message.text = "какой вуз выбрать?"
    state = AsyncMock()
    state.get_data.return_value = {"scenario": "university"}
    ready = (
        "ЗП &lt; 100К &amp; R&amp;D\n\n"
        "📚 <b>Источники</b>\n"
        '• <a href="https://rabota.x5.ru/">X5 Group</a> — rabota.x5.ru'
    )

    with patch.object(info, "answer_info_question", AsyncMock(return_value=ready)), \
            patch.object(info, "get_or_create_user", AsyncMock(return_value={"language": "ru", "voice_enabled": 0})):
        await info.handle_text_message(mock_message, state)

    text = mock_message.answer.await_args.args[0]
    assert "&lt; 100К" in text
    assert '<b>Источники</b>' in text
    assert '<a href="https://rabota.x5.ru/">X5 Group</a>' in text
    assert "&lt;a href" not in text


@pytest.mark.asyncio
async def test_answer_info_escapes_only_ai_text(monkeypatch):
    """Экранируется только текст GigaChat, источники остаются разметкой"""
    from types import SimpleNamespace

    import bot.core.scenarios as scenarios

    doc = SimpleNamespace(
        metadata={"source_url": "https://rabota.x5.ru/", "title": "X5 Group"},
        page_content="стажировки",
    )
    monkeypatch.setattr(scenarios, "search", lambda *args, **kwargs: [doc])
    monkeypatch.setattr(
        scenarios,
        "ask_ai",
        AsyncMock(return_value="Стажировки в X5: ЗП < 100К & R&D. Требования: Python и SQL, "
                               "портфолио из двух проектов, готовность к интервью."),
    )

    answer = await scenarios.answer_info_question("стажировки?", "job")

    assert "&lt; 100К" in answer
    assert "&amp; R&amp;D" in answer
    assert '<a href="https://rabota.x5.ru/">X5 Group</a>' in answer
    assert "&lt;a href" not in answer

@pytest.mark.asyncio
async def test_open_exam_feedback_with_html_chars_is_escaped(test_db, mock_message):
    await get_or_create_user(UID)
    session_id = await create_session(UID, "job", "examiner", 1)
    mock_message.from_user.id = UID
    mock_message.text = "тестовый ответ"

    examiner.exam_sessions[UID] = {
        "scenario": "job",
        "cases": [{
            "type": "open",
            "situation": "Дима на стажировке",
            "question": "Что делать?",
            "good_answer_points": [],
            "common_mistakes": [],
        }],
        "current": 0,
        "total": 1,
        "session_id": session_id,
        "answers": [],
        "scores": [],
        "timestamp": 9e9,
        "chat_id": UID,
        "case_msg_id": None,
        "feedback_msg_id": None,
    }

    evaluation = {
        "score": 2,
        "feedback": "Плохо: <b>нет фактов</b> & R&D",
        "strengths": ["<script>alert(1)</script>"],
        "weaknesses": ["мало <фактов>"],
        "example_answer": "Скажи <нет>",
        "source": "",
        "sources": [],
    }

    try:
        with patch.object(examiner, "evaluate_answer", AsyncMock(return_value=evaluation)), \
                patch.object(examiner, "_translate_if_needed", AsyncMock(side_effect=lambda text, lang: text)), \
                patch.object(examiner, "record_error"):
            await examiner.handle_exam_answer(mock_message, AsyncMock())

        text = mock_message.answer.await_args.args[0]
        assert "&lt;b&gt;нет фактов&lt;/b&gt; &amp; R&amp;D" in text
        assert "&lt;script&gt;" in text
        assert "<script>" not in text
        assert "&lt;фактов&gt;" in text
        assert "Скажи &lt;нет&gt;" in text
    finally:
        examiner.exam_sessions.pop(UID, None)


@pytest.mark.asyncio
async def test_choice_exam_feedback_with_html_chars_is_escaped(test_db, mock_callback):
    await get_or_create_user(UID)
    session_id = await create_session(UID, "job", "examiner", 1)
    mock_callback.from_user.id = UID
    mock_callback.data = "answer_choice_1"
    mock_callback.message.answer.reset_mock()

    examiner.exam_sessions[UID] = {
        "scenario": "job",
        "cases": [{
            "type": "choice",
            "situation": "Катя выбирает курс",
            "question": "Что лучше?",
            "options": ["Курс <A>", "Курс B", "Курс C", "Курс D"],
            "correct": 0,
            "explanation": "Потому что <A> дешевле & быстрее",
        }],
        "current": 0,
        "total": 1,
        "session_id": session_id,
        "answers": [],
        "scores": [],
        "timestamp": 9e9,
        "chat_id": UID,
        "case_msg_id": None,
        "feedback_msg_id": None,
    }

    try:
        with patch.object(examiner, "record_error"):
            await examiner.cb_answer_choice(mock_callback, AsyncMock())

        text = mock_callback.message.answer.await_args.args[0]
        assert "Курс &lt;A&gt;" in text
        assert "&amp; быстрее" in text
    finally:
        examiner.exam_sessions.pop(UID, None)

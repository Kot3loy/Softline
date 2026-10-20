"""Итоги экзамена: слабые задания должны быть видны сразу, а не со второй сессии."""

from unittest.mock import patch

import pytest

from bot.core.adaptive import get_recommendations
from bot.handlers import examiner
from bot.translations import t

UID = 424242


def _case(question):
    return {
        "type": "open",
        "situation": "Ситуация",
        "question": question,
        "good_answer_points": [],
        "common_mistakes": [],
    }


def _session(questions, scores):
    return {
        "scenario": "job",
        "cases": [_case(q) for q in questions],
        "current": len(questions) - 1,
        "total": len(questions),
        "session_id": None,
        "answers": [
            {
                "case_idx": i,
                "user_answer": "не знаю",
                "evaluation": {"score": scores[i], "feedback": "слабо"},
            }
            for i in range(len(questions))
        ],
        "scores": scores,
        "timestamp": 9e9,
        "chat_id": UID,
        "case_msg_id": None,
        "feedback_msg_id": None,
    }


@pytest.fixture
def empty_errors(tmp_path):
    errors_file = tmp_path / "learning_errors.json"
    errors_file.write_text("{}", encoding="utf-8")
    with patch("bot.core.adaptive.ERRORS_FILE", errors_file):
        yield errors_file


@pytest.mark.asyncio
async def test_low_score_report_lists_weak_tasks(test_db, mock_message, empty_errors):
    session = _session(
        ["Что ответить на заниженную зарплату?", "Как поступить с токсичным коллегой?"],
        [2, 3],
    )

    await examiner._finalize_exam(UID, session, mock_message, "ru")
    text = mock_message.answer.await_args.args[0]

    # 2 из 10 — это точно не «нет слабых областей»
    assert t("adaptive_no_weak", "ru") not in text
    assert "2/10" in text
    assert "Что ответить на заниженную зарплату?" in text


@pytest.mark.asyncio
async def test_high_score_report_keeps_no_weak_message(test_db, mock_message, empty_errors):
    session = _session(["Что ответить?", "Как поступить?"], [9, 10])

    await examiner._finalize_exam(UID, session, mock_message, "ru")
    text = mock_message.answer.await_args.args[0]

    assert t("adaptive_no_weak", "ru") in text
    assert "9/10" not in text


def test_recommendations_use_current_session_results(empty_errors):
    recs = get_recommendations(
        UID,
        "university",
        "ru",
        session_results=[{"number": 1, "topic": "Выбор вуза", "score": 2}],
    )

    assert any("2/10" in rec for rec in recs)
    assert not any(t("adaptive_no_weak", "ru") in rec for rec in recs)

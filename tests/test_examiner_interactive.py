"""Экзаменатор: интерактивные тесты с вариантами, валидация, защита от двойного клика."""

import pytest
from unittest.mock import AsyncMock, patch

from bot.handlers import examiner


def _choice(situation="s", question="q", options=None, correct=0):
    return {
        "type": "choice",
        "situation": situation,
        "question": question,
        "options": options if options is not None else ["A", "B", "C", "D"],
        "correct": correct,
        "explanation": "e",
    }


def _open(situation="s", question="q"):
    return {
        "type": "open",
        "situation": situation,
        "question": question,
        "good_answer_points": [],
        "common_mistakes": [],
    }


# --- валидация сгенерированного теста ---

def test_valid_choice_accepts_good_case():
    assert examiner._valid_choice(_choice()) is True


@pytest.mark.parametrize(
    "case",
    [
        _choice(options=["A", "A", "B", "C"]),           # дубли
        _choice(options=["A", "B", "C", ""]),            # пустой вариант
        _choice(options=["A", "B", "C"]),                # не 4 варианта
        _choice(correct=4),                              # индекс вне диапазона
        _choice(correct="0"),                            # индекс не число
        _choice(question=""),                            # нет вопроса
        _open(),                                         # это не тест
        {"type": "choice", "situation": "s", "question": "q", "options": "A,B,C,D", "correct": 0},
    ],
)
def test_valid_choice_rejects_broken_case(case):
    assert examiner._valid_choice(case) is False


# --- каждый второй кейс — тест ---

def test_choice_case_type_is_every_second():
    types = [examiner._choice_case_type(i) for i in range(5)]
    assert types == ["open", "choice", "open", "choice", "open"]


@pytest.mark.asyncio
async def test_start_exam_generates_half_choice_cases(test_db, mock_callback):
    uid = mock_callback.from_user.id
    mock_callback.data = "cases_5"

    async def fake_generate(scenario, difficulty="medium", weak_areas=None, case_type="open"):
        return _choice() if case_type == "choice" else _open()

    try:
        with patch.object(examiner, "generate_case", side_effect=fake_generate), \
                patch.object(examiner, "get_weak_areas", lambda *a, **k: []), \
                patch("bot.core.ai_engine.clear_history", new_callable=AsyncMock):
            await examiner.cb_start_exam(mock_callback, AsyncMock())

        cases = examiner.exam_sessions[uid]["cases"]
        assert [c["type"] for c in cases] == ["open", "choice", "open", "choice", "open"]
    finally:
        examiner.exam_sessions.pop(uid, None)


@pytest.mark.asyncio
async def test_invalid_choice_falls_back_to_open_case(test_db, mock_callback):
    # ai отдал битый тест (дубли вариантов) — переспрашиваем, потом обычный вопрос
    uid = mock_callback.from_user.id
    mock_callback.data = "cases_3"
    calls = []

    async def fake_generate(scenario, difficulty="medium", weak_areas=None, case_type="open"):
        calls.append(case_type)
        if case_type == "choice":
            return _choice(options=["A", "A", "B", "C"])
        return _open(situation="открытый")

    try:
        with patch.object(examiner, "generate_case", side_effect=fake_generate), \
                patch.object(examiner, "get_weak_areas", lambda *a, **k: []), \
                patch("bot.core.ai_engine.clear_history", new_callable=AsyncMock):
            await examiner.cb_start_exam(mock_callback, AsyncMock())

        cases = examiner.exam_sessions[uid]["cases"]
        # битый тест не показан: на его месте обычный открытый вопрос
        assert all(c["type"] == "open" for c in cases)
        assert calls.count("choice") >= 2  # была попытка перегенерировать тест
    finally:
        examiner.exam_sessions.pop(uid, None)


@pytest.mark.asyncio
async def test_valid_choice_from_retry_is_used(test_db, mock_callback):
    uid = mock_callback.from_user.id
    mock_callback.data = "cases_3"

    # первая генерация теста битая, повторная — валидная
    state = {"n": 0}

    async def smarter_generate(scenario, difficulty="medium", weak_areas=None, case_type="open"):
        if case_type != "choice":
            return _open()
        state["n"] += 1
        return _choice(options=["A", "B", "C"]) if state["n"] == 1 else _choice()

    try:
        with patch.object(examiner, "generate_case", side_effect=smarter_generate), \
                patch.object(examiner, "get_weak_areas", lambda *a, **k: []), \
                patch("bot.core.ai_engine.clear_history", new_callable=AsyncMock):
            await examiner.cb_start_exam(mock_callback, AsyncMock())

        cases = examiner.exam_sessions[uid]["cases"]
        assert cases[1]["type"] == "choice"
        assert cases[1]["options"] == ["A", "B", "C", "D"]
    finally:
        examiner.exam_sessions.pop(uid, None)


# --- подсказка и разметка ---

def test_choice_marks_show_correct_and_chosen():
    case = _choice(options=["A", "B", "C", "D"], correct=1)
    marks = examiner._choice_marks(case, chosen_idx=2)
    assert marks == ["▫️ A", "✅ B", "❌ C", "▫️ D"]

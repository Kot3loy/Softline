"""Парсер текстовых ответов GigaChat и защита от повторяющихся заданий."""

import json

import pytest

from bot.core import ai_engine
from bot.core.ai_engine import _parse_text_response, case_signature, generate_case


# ответ GigaChat живьём: json он игнорирует и отдаёт текст с английскими метками
GIGACHAT_CHOICE_TEXT = (
    "Ситуация: Катя собирается поступать в университет и изучает рейтинги вузов. "
    "Она видит, что один вуз имеет высокие оценки по преподавателям и инфраструктуре, "
    "но низкие по трудоустройству выпускников. Какой критерий ей стоит учесть прежде всего?\n\n"
    "Вопрос: Какой фактор наиболее важен при выборе университета?\n\n"
    "Options:\n"
    "- Высокие оценки преподавателей\n"
    "- Развитая инфраструктура\n"
    "- Хорошее трудоустройство выпускников\n"
    "- Близость к дому\n\n"
    "Correct: 3\n"
    "Explanation: Поскольку Катя планирует учиться и работать по специальности, "
    "важно, чтобы вуз обеспечивал успешное трудоустройство выпускников."
)


# --- парсер текстового ответа ---

def test_gigachat_bullet_options_become_choice_case():
    case = _parse_text_response(GIGACHAT_CHOICE_TEXT, "choice")

    assert case["type"] == "choice"
    assert case["options"] == [
        "Высокие оценки преподавателей",
        "Развитая инфраструктура",
        "Хорошее трудоустройство выпускников",
        "Близость к дому",
    ]
    # "Correct: 3" — счёт с единицы, третий вариант "Хорошее трудоустройство"
    assert case["correct"] == 2
    assert case["question"] == "Какой фактор наиболее важен при выборе университета?"
    assert case["situation"].startswith("Катя собирается поступать")
    assert case["explanation"].startswith("Поскольку Катя планирует")


def test_numbered_options_and_numeric_correct():
    text = (
        "Ситуация: Дима выбирает курс.\n"
        "Вопрос: Какой курс ему подойдёт?\n"
        "Варианты:\n"
        "1. 420 рублей\n"
        "2. 360 рублей\n"
        "3. 240 рублей\n"
        "4. 180 рублей\n"
        "Правильный ответ: 3\n"
        "Подсказка: скидка 30%"
    )
    case = _parse_text_response(text, "choice")

    assert case["type"] == "choice"
    assert case["options"] == ["420 рублей", "360 рублей", "240 рублей", "180 рублей"]
    assert case["correct"] == 2
    assert case["hint"] == "скидка 30%"


def test_correct_as_letter():
    text = (
        "Ситуация: Аня на собеседовании.\n"
        "Вопрос: Что ответить?\n"
        "Options:\n"
        "- Согласиться сразу\n"
        "- Уточнить условия\n"
        "- Уйти молча\n"
        "- Позвонить маме\n"
        "Correct: B\n"
        "Explanation: Условия важнее скорости."
    )
    case = _parse_text_response(text, "choice")

    assert case["type"] == "choice"
    assert case["correct"] == 1
    assert case["explanation"] == "Условия важнее скорости."


def test_english_section_labels_are_understood():
    text = (
        "Situation: Дима пришёл стажёром.\n"
        "Question: Как поступить?\n"
        "Hint: спроси наставника"
    )
    case = _parse_text_response(text, "open")

    assert case["type"] == "open"
    assert case["situation"] == "Дима пришёл стажёром."
    assert case["question"] == "Как поступить?"
    assert case["hint"] == "спроси наставника"


def test_open_case_ignores_option_sections():
    text = (
        "Ситуация: Саша получил оффер.\n"
        "Вопрос: Принимать ли?\n"
        "Hint: сравни условия"
    )
    case = _parse_text_response(text, "open")

    assert case["type"] == "open"
    assert "options" not in case
    assert case["hint"] == "сравни условия"


# --- антиповтор: прошлые задания уходят в промпт ---

@pytest.fixture
def no_rag(monkeypatch):
    monkeypatch.setattr(ai_engine, "search", lambda *a, **k: [])
    monkeypatch.setattr(ai_engine, "RETRY_DELAY", 0)


@pytest.mark.asyncio
async def test_generate_case_passes_avoid_list_to_prompt(no_rag, monkeypatch):
    captured = {}

    async def fake_ask(prompt, system_prompt="", max_tokens=700, strip_md=False):
        captured["prompt"] = prompt
        captured["system"] = system_prompt
        return json.dumps(
            {
                "type": "open",
                "situation": "Дима на стажировке получил срочную задачу",
                "question": "Как поступить?",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(ai_engine, "ask_ai", fake_ask)

    await generate_case(
        "university",
        case_type="choice",
        avoid=["Катя выбирает вуз между Москвой и Питером"],
    )

    text = captured["prompt"] + captured["system"]
    assert "НЕ ПОВТОРЯЙ" in text
    assert "Катя выбирает вуз между Москвой и Питером" in text


@pytest.mark.asyncio
async def test_generate_case_regenerates_similar_case(no_rag, monkeypatch):
    duplicate = {
        "type": "open",
        "situation": "Катя выбирает университет между Москвой и Питером",
        "question": "Что ей делать?",
    }
    fresh = {
        "type": "open",
        "situation": "Дима на стажировке получил срочную задачу",
        "question": "Как поступить?",
    }
    answers = [json.dumps(duplicate, ensure_ascii=False), json.dumps(fresh, ensure_ascii=False)]
    calls = []

    async def fake_ask(prompt, system_prompt="", max_tokens=700, strip_md=False):
        calls.append(prompt)
        return answers[min(len(calls) - 1, len(answers) - 1)]

    monkeypatch.setattr(ai_engine, "ask_ai", fake_ask)

    case = await generate_case("university", avoid=[case_signature(duplicate)])

    assert case["situation"].startswith("Дима")
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_generate_case_accepts_repeat_on_last_attempt(no_rag, monkeypatch):
    duplicate = {
        "type": "open",
        "situation": "Катя выбирает университет между Москвой и Питером",
        "question": "Что ей делать?",
    }
    calls = []

    async def fake_ask(prompt, system_prompt="", max_tokens=700, strip_md=False):
        calls.append(prompt)
        return json.dumps(duplicate, ensure_ascii=False)

    monkeypatch.setattr(ai_engine, "ask_ai", fake_ask)

    case = await generate_case("university", avoid=[case_signature(duplicate)])

    # лучше показать похожий кейс, чем упасть в "не удалось сгенерировать"
    assert case["situation"] == duplicate["situation"]
    assert len(calls) == ai_engine.MAX_RETRIES

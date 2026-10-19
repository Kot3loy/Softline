import pytest
from bot.core.ai_engine import _parse_json, _parse_text_response


def test_parse_json_valid():
    """Тест парсинга валидного JSON"""
    text = '{"score": 7, "feedback": "Хорошо"}'
    result = _parse_json(text, {})
    assert result["score"] == 7
    assert result["feedback"] == "Хорошо"


def test_parse_json_in_code_block():
    """Тест парсинга JSON в markdown code block"""
    text = '```json\n{"score": 8, "feedback": "Отлично"}\n```'
    result = _parse_json(text, {})
    assert result["score"] == 8


def test_parse_json_invalid():
    """Тест парсинга невалидного JSON"""
    text = "Это не JSON"
    result = _parse_json(text, {"default": True})
    assert result["default"] is True


def test_parse_json_nested():
    """Тест парсинга JSON с вложенными объектами"""
    text = '{"strengths": ["сил1", "сил2"], "weaknesses": ["слаб1"]}'
    result = _parse_json(text, {})
    assert len(result["strengths"]) == 2
    assert len(result["weaknesses"]) == 1


def test_parse_json_partial_match():
    """Тест парсинга когда JSON внутри текста"""
    text = 'Вот результат: {"score": 5} конец'
    result = _parse_json(text, {})
    assert result.get("score") == 5


def test_parse_text_response_open():
    """Тест парсинга текстового формата (open case)"""
    text = (
        "Ситуация: Дима пришёл стажёром. Начальник кричит на него при коллегах.\n"
        "Вопрос: Как поступить Диме?"
    )
    result = _parse_text_response(text, "open")
    assert result["situation"] == "Дима пришёл стажёром. Начальник кричит на него при коллегах."
    assert result["question"] == "Как поступить Диме?"
    assert result["type"] == "open"


def test_parse_text_response_choice():
    """Тест парсинга текстового формата (choice case)"""
    text = (
        "Ситуация: Катя на собеседовании.\n"
        "Вопрос: Что лучше?\n"
        "A. Позвонить менеджеру\n"
        "B. Написать письмо\n"
        "C. Спросить коллегу\n"
        "D. Подождать до утра\n"
        "Правильный ответ: B\n"
        "Объяснение: Потому что B"
    )
    result = _parse_text_response(text, "choice")
    assert result["situation"] == "Катя на собеседовании."
    assert result["question"] == "Что лучше?"
    assert result["options"] == ["Позвонить менеджеру", "Написать письмо", "Спросить коллегу", "Подождать до утра"]
    assert result["correct"] == 1
    assert result["type"] == "choice"


def test_parse_text_response_choice_without_real_options_becomes_open():
    """Буквенные заглушки вместо ответов — это не тест, задаём обычный вопрос"""
    text = (
        "Ситуация: Катя на собеседовании.\n"
        "Вопрос: Что лучше?\n"
        "A. Вариант A\n"
        "B. Вариант B\n"
        "C. Вариант C\n"
        "D. Вариант D\n"
        "Правильный ответ: B"
    )
    result = _parse_text_response(text, "choice")
    assert result["type"] == "open"


def test_parse_text_response_choice_pulls_options_out_of_question():
    """Варианты перечислены в строке вопроса — вытаскиваем их в options"""
    text = (
        "Ситуация: Катя считает скидку.\n"
        "Вопрос: Какой ценой воспользоваться? A) 420 рублей; B) 360 рублей; C) 240 рублей; D) 180 рублей?\n"
        "Правильный ответ: A"
    )
    result = _parse_text_response(text, "choice")
    assert result["question"] == "Какой ценой воспользоваться?"
    assert result["options"] == ["420 рублей", "360 рублей", "240 рублей", "180 рублей"]



def test_parse_text_response_empty():
    """Тест парсинга пустого ответа"""
    result = _parse_text_response("", "open")
    assert result == {}

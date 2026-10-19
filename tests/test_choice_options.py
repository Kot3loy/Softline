"""Варианты ответа: настоящие ответы вместо буквенных заглушек от LLM."""

import pytest

from bot.core.choice_options import (
    clean_question,
    is_placeholder_options,
    normalize_choice_case,
    split_lettered_options,
)


def test_split_options_written_in_one_line():
    # LLM пишет варианты прямо в вопрос — вытаскиваем их оттуда
    head, options = split_lettered_options(
        "Какой итоговой ценой воспользоваться? "
        "A) 420 рублей; B) 360 рублей; C) 240 рублей; D) 180 рублей?"
    )
    assert head == "Какой итоговой ценой воспользоваться?"
    assert options == ["420 рублей", "360 рублей", "240 рублей", "180 рублей"]


def test_split_options_written_on_separate_lines():
    head, options = split_lettered_options(
        "Что лучше?\n"
        "A) Первый вариант\n"
        "B) Второй вариант\n"
        "C) Третий вариант\n"
        "D) Четвёртый вариант"
    )
    assert head == "Что лучше?"
    assert options == ["Первый вариант", "Второй вариант", "Третий вариант", "Четвёртый вариант"]


def test_split_options_needs_all_four():
    text = "Что делать? A) Первый; B) Второй"
    head, options = split_lettered_options(text)
    assert options == []
    assert head == text


@pytest.mark.parametrize(
    "options",
    [
        ["Вариант A", "Вариант B", "Вариант C", "Вариант D"],
        ["A", "B", "C", "D"],
        ["Ответ 1", "Ответ 2", "Ответ 3", "Ответ 4"],
        ["Один", "Один", "Два", "Три"],
        ["Один", "Два", "Три"],
        "Один, Два, Три, Четыре",
        None,
    ],
)
def test_placeholders_detected(options):
    assert is_placeholder_options(options) is True


def test_real_options_are_not_placeholders():
    assert is_placeholder_options(["420 рублей", "360 рублей", "240 рублей", "180 рублей"]) is False


def test_normalize_replaces_placeholders_with_inline_options():
    case = normalize_choice_case({
        "type": "choice",
        "situation": "Катя считает скидку",
        "question": "Какой ценой воспользоваться? A) 420 рублей; B) 360 рублей; C) 240 рублей; D) 180 рублей?",
        "options": ["Вариант A", "Вариант B", "Вариант C", "Вариант D"],
        "correct": 0,
    })
    assert case["type"] == "choice"
    assert case["question"] == "Какой ценой воспользоваться?"
    assert case["options"] == ["420 рублей", "360 рублей", "240 рублей", "180 рублей"]


def test_normalize_keeps_real_options():
    case = normalize_choice_case({
        "type": "choice",
        "situation": "s",
        "question": "Что делать?",
        "options": ["Позвонить менеджеру", "Написать письмо", "Спросить коллегу", "Подождать"],
        "correct": 2,
    })
    assert case["type"] == "choice"
    assert case["options"][2] == "Спросить коллегу"


def test_normalize_degrades_broken_test_to_open():
    # битый тест не показываем: пусть экзаменатор задаст обычный вопрос
    case = normalize_choice_case({
        "type": "choice",
        "situation": "s",
        "question": "Что делать?",
        "options": ["Вариант A", "Вариант B", "Вариант C", "Вариант D"],
        "correct": 0,
    })
    assert case["type"] == "open"


def test_clean_question_removes_double_marks_and_spaces():
    assert clean_question("  Что   лучше??  ") == "Что лучше?"

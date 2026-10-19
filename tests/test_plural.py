"""Числительные: «1 задание», «3 задания», «5 заданий»."""

import pytest

from bot.translations import t
from bot.utils.plural import noun, plural_ru


@pytest.mark.parametrize(
    "n,expected",
    [
        (1, "задание"),
        (2, "задания"),
        (3, "задания"),
        (4, "задания"),
        (5, "заданий"),
        (0, "заданий"),
        (11, "заданий"),
        (12, "заданий"),
        (14, "заданий"),
        (21, "задание"),
        (22, "задания"),
        (25, "заданий"),
        (101, "задание"),
        (111, "заданий"),
    ],
)
def test_plural_ru_tasks(n, expected):
    assert plural_ru(n, "задание", "задания", "заданий") == expected


def test_noun_sessions_ru():
    assert noun(1, "ru", "session") == "сессия"
    assert noun(3, "ru", "session") == "сессии"
    assert noun(5, "ru", "session") == "сессий"


def test_noun_english():
    assert noun(1, "en", "task") == "task"
    assert noun(3, "en", "task") == "tasks"
    assert noun(0, "en", "task") == "tasks"


def test_noun_unknown_key_falls_back_to_task():
    assert noun(3, "ru", "no_such_noun") == "задания"


def test_exam_start_strings_are_grammatical():
    assert "3 задания" in t("exam_start", "ru", n=3, noun=noun(3, "ru", "task"))
    assert "1 задание" in t("exam_start", "ru", n=1, noun=noun(1, "ru", "task"))
    assert "5 заданий" in t("exam_start", "ru", n=5, noun=noun(5, "ru", "task"))
    assert "3 tasks" in t("exam_start", "en", n=3, noun=noun(3, "en", "task"))


def test_progress_line_strings_are_grammatical():
    assert "3 сессии" in t("progress_scenario_line", "ru", name="X", sessions=3,
                           avg=7, noun=noun(3, "ru", "session"))
    assert "1 сессия" in t("progress_scenario_line", "ru", name="X", sessions=1,
                           avg=7, noun=noun(1, "ru", "session"))


def test_exam_cases_choice_uses_plural():
    from bot.utils.keyboards import exam_cases_kb

    texts = [button.text for row in exam_cases_kb("ru").inline_keyboard for button in row]
    assert "3 задания" in texts
    assert "5 заданий" in texts
    assert "10 заданий" in texts

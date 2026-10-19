import pytest
from bot.utils.keyboards import (
    main_menu_kb,
    settings_kb,
    scenario_info_kb,
    exam_cases_kb,
    case_answer_kb,
    choice_answer_kb,
    back_to_menu_kb,
)


def test_main_menu_kb():
    """Тест главного меню"""
    kb = main_menu_kb()
    assert kb is not None
    assert len(kb.keyboard) == 4  # 4 строки: 3 сценария + прогресс/настройки


def test_settings_kb():
    """Тест клавиатуры настроек"""
    # Голос выключен
    kb = settings_kb(voice_enabled=False)
    assert kb is not None
    assert len(kb.inline_keyboard) == 4  # голос, язык (2 кнопки), о боте, назад
    assert "Выкл" in kb.inline_keyboard[0][0].text
    # Язык — строка с двумя кнопками
    lang_row = kb.inline_keyboard[1]
    assert len(lang_row) == 2
    lang_texts = [b.text for b in lang_row]
    assert any("RU" in t for t in lang_texts)
    assert any("EN" in t for t in lang_texts)

    # Голос включён
    kb = settings_kb(voice_enabled=True)
    assert "Вкл" in kb.inline_keyboard[0][0].text


def test_scenario_info_kb():
    """Тест клавиатуры сценария"""
    kb = scenario_info_kb("university")
    assert kb is not None
    assert len(kb.inline_keyboard) == 3  # 3 кнопки


def test_exam_cases_kb():
    """Тест клавиатуры выбора кейсов"""
    kb = exam_cases_kb()
    assert kb is not None
    assert len(kb.inline_keyboard) == 2  # 2 строки


def test_case_answer_kb():
    """Тест клавиатуры ответа на задание"""
    # Не последнее задание — только кнопка "Следующее"
    kb = case_answer_kb(1, 5)
    assert kb is not None
    assert len(kb.inline_keyboard) == 1
    assert kb.inline_keyboard[0][0].callback_data == "next_case"

    # Последнее задание — кнопка "Завершить"
    kb = case_answer_kb(5, 5)
    assert kb is not None
    assert len(kb.inline_keyboard) == 1
    assert kb.inline_keyboard[0][0].callback_data == "show_results"


def test_choice_answer_kb():
    """Тест клавиатуры выбора ответа: варианты показаны в тексте, кнопки — буквы"""
    options = ["420 рублей", "360 рублей", "240 рублей", "180 рублей"]
    kb = choice_answer_kb(options)
    assert kb is not None
    assert len(kb.inline_keyboard) == 4  # 4 кнопки

    # Проверяем что callback_data правильный
    for i, row in enumerate(kb.inline_keyboard):
        assert row[0].callback_data == f"answer_choice_{i}"

    # Кнопки короткие — сами варианты уже есть в тексте задания
    assert [row[0].text for row in kb.inline_keyboard] == ["A", "B", "C", "D"]

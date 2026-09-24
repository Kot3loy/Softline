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

    # Последнее задание — только "Результаты"
    kb = case_answer_kb(5, 5)
    assert kb is not None
    assert len(kb.inline_keyboard) == 1


def test_choice_answer_kb():
    """Тест клавиатуры выбора ответа (4 варианта A/B/C/D)"""
    options = ["Вариант A", "Вариант B", "Вариант C", "Вариант D"]
    kb = choice_answer_kb(options)
    assert kb is not None
    assert len(kb.inline_keyboard) == 4  # 4 кнопки

    # Проверяем что callback_data правильный
    for i, row in enumerate(kb.inline_keyboard):
        assert row[0].callback_data == f"answer_choice_{i}"

    # Проверяем что буквы A/B/C/D в тексте
    texts = [row[0].text for row in kb.inline_keyboard]
    assert texts[0].startswith("A.")
    assert texts[1].startswith("B.")
    assert texts[2].startswith("C.")
    assert texts[3].startswith("D.")

"""Генерация клавиатур — Reply и Inline кнопки для всех режимов бота."""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb():
    """Главное меню — три сценария + настройки"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎓 Выбор вуза")],
            [KeyboardButton(text="💼 Поиск работы")],
            [KeyboardButton(text="🤝 Адаптация в компании")],
            [KeyboardButton(text="📊 Прогресс"), KeyboardButton(text="⚙️ Настройки")],
        ],
        resize_keyboard=True,
    )


def settings_kb(voice_enabled: bool = False):
    """Inline клавиатура настроек"""
    voice_text = "🔊 Голос: Вкл" if voice_enabled else "🔊 Голос: Выкл"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=voice_text, callback_data="settings_voice")],
            [InlineKeyboardButton(text="ℹ️ О боте", callback_data="settings_about")],
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_menu")],
        ]
    )


def scenario_info_kb(scenario: str):
    """Кнопки внутри сценария — инфо режим или экзаменатор"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📚 Информационный режим", callback_data=f"info_{scenario}")],
            [InlineKeyboardButton(text="🎯 Режим экзаменатора", callback_data=f"exam_{scenario}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")],
        ]
    )


def exam_cases_kb():
    """Выбор количества заданий"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="3 задания", callback_data="cases_3"),
                InlineKeyboardButton(text="5 заданий", callback_data="cases_5"),
                InlineKeyboardButton(text="10 заданий", callback_data="cases_10"),
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")],
        ]
    )


def case_answer_kb(case_num: int, total: int):
    """Кнопки после ответа на задание — следующий или завершить"""
    buttons = []
    if case_num < total:
        buttons.append([InlineKeyboardButton(text="▶ Следующее задание", callback_data="next_case")])
    else:
        buttons.append([InlineKeyboardButton(text="📊 Результаты", callback_data="show_results")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_to_menu_kb():
    """Кнопка возврата в главное меню"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_menu")]
        ]
    )


def choice_answer_kb(options: list, case_num: int, total: int):
    """Клавиатура с вариантами ответа (4 кнопки A/B/C/D)"""
    letters = ["A", "B", "C", "D"]
    buttons = []
    for i, option in enumerate(options[:4]):
        buttons.append([
            InlineKeyboardButton(
                text=f"{letters[i]}. {option}",
                callback_data=f"answer_choice_{i}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

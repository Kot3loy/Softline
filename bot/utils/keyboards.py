# все клавиатуры бота (reply + inline)

import logging
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from bot.translations import t
from bot.utils.plural import noun

logger = logging.getLogger(__name__)


def main_menu_kb(lang: str = "ru"):
    # главное меню
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_university", lang))],
            [KeyboardButton(text=t("btn_job", lang))],
            [KeyboardButton(text=t("btn_adaptation", lang))],
            [KeyboardButton(text=t("btn_progress", lang)), KeyboardButton(text=t("btn_settings", lang))],
        ],
        resize_keyboard=True,
    )


def settings_kb(voice_enabled: bool = False, lang: str = "ru"):
    # клавиатура настроек
    voice_text = t("voice_on", lang) if voice_enabled else t("voice_off", lang)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=voice_text, callback_data="settings_voice")],
            [
                InlineKeyboardButton(text=t("btn_language_ru", lang), callback_data="set_lang_ru"),
                InlineKeyboardButton(text=t("btn_language_en", lang), callback_data="set_lang_en"),
            ],
            [InlineKeyboardButton(text=t("btn_about", lang), callback_data="settings_about")],
            [InlineKeyboardButton(text=t("btn_back", lang), callback_data="back_to_menu")],
        ]
    )


def scenario_info_kb(scenario: str, lang: str = "ru"):
    # кнопки выбора режима внутри сценария
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_info_mode", lang), callback_data=f"info_{scenario}")],
            [InlineKeyboardButton(text=t("btn_exam_mode", lang), callback_data=f"exam_{scenario}")],
            [InlineKeyboardButton(text=t("btn_back_short", lang), callback_data="back_to_menu")],
        ]
    )


def exam_cases_kb(lang: str = "ru"):
    # сколько заданий потянет юзер
    def _case_button(count: int):
        return InlineKeyboardButton(
            text=t("exam_cases", lang, n=count, noun=noun(count, lang, "task")),
            callback_data=f"cases_{count}",
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_case_button(3), _case_button(5), _case_button(10)],
            [InlineKeyboardButton(text=t("btn_back_short", lang), callback_data="back_to_menu")],
        ]
    )


def case_answer_kb(case_num: int, total: int, lang: str = "ru"):
    # кнопки "дальше" / "завершить"
    if case_num < total:
        button = InlineKeyboardButton(text=t("exam_next", lang), callback_data="next_case")
    else:
        button = InlineKeyboardButton(text=t("exam_finish", lang), callback_data="show_results")
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


def back_to_menu_kb(lang: str = "ru"):
    # назад в меню
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_back", lang), callback_data="back_to_menu")]
        ]
    )


def choice_answer_kb(options: list):
    # варианты показаны в тексте задания, поэтому кнопки короткие — буквы
    letters = ["A", "B", "C", "D"]
    if len(options) > 4:
        logger.warning(f"Больше 4 вариантов ({len(options)}), обрезаю до 4")
    buttons = []
    for i in range(min(len(options), 4)):
        buttons.append([
            InlineKeyboardButton(
                text=letters[i],
                callback_data=f"answer_choice_{i}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def progress_kb(lang: str = "ru"):
    # кнопки для экрана прогресса
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("progress_reset_btn", lang), callback_data="progress_reset")],
            [InlineKeyboardButton(text=t("btn_back", lang), callback_data="back_to_menu")],
        ]
    )

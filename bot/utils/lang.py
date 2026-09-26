# утилиты по языкам: какой язык у юзера + список известных кнопок

from bot.translations import t


def get_lang(user_data: dict | None = None) -> str:
    return user_data.get("language", "ru") if user_data else "ru"


KNOWN_BUTTONS = set()
for _l in ("ru", "en"):
    KNOWN_BUTTONS.update([
        t("btn_university", _l), t("btn_job", _l), t("btn_adaptation", _l),
        t("btn_progress", _l), t("btn_settings", _l), t("btn_about", _l),
        t("voice_on", _l), t("voice_off", _l),
    ])

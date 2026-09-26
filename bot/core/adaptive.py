# запоминаю ошибки пользователя и потом подкалывать задания по слабым темам

import logging
import json
import tempfile
import os
from bot.config import config
from bot.translations import t

logger = logging.getLogger(__name__)

# Файл для хранения данных об ошибках
ERRORS_FILE = config.DATA_DIR / "learning_errors.json"


def _load_errors() -> dict:
    # читаю learning_errors.json
    if ERRORS_FILE.exists():
        try:
            with open(ERRORS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки данных об ошибках: {e}")
    return {}


def _save_errors(data: dict):
    # сначала пишу во временный файл, потом переименовываю —
    # если бот упадёт посреди записи, старый файл не сгорит
    try:
        ERRORS_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=ERRORS_FILE.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(ERRORS_FILE))
        except Exception:
            # если не получилось — просто убираем временный файл
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
    except Exception as e:
        logger.error(f"Ошибка сохранения данных об ошибках: {e}")


def record_error(user_id: int, case_id: str, scenario: str, score: int):
    # записываю попытку пользователя по кейсу
    data = _load_errors()

    if str(user_id) not in data:
        data[str(user_id)] = {}

    user_data = data[str(user_id)]
    if scenario not in user_data:
        user_data[scenario] = {}

    # обновляю статистику по кейсу
    if case_id not in user_data[scenario]:
        user_data[scenario][case_id] = {
            "attempts": 0,
            "total_score": 0,
            "errors": [],
        }

    case_stats = user_data[scenario][case_id]
    case_stats["attempts"] += 1
    case_stats["total_score"] += score

    # если балл низкий (< 6) — добавляю в список ошибок
    if score < 6:
        case_stats["errors"].append({
            "score": score,
            "attempt": case_stats["attempts"],
        })

    _save_errors(data)
    logger.info(f"Записана ошибка: user={user_id}, case={case_id}, score={score}")


# Минимум попыток, прежде чем считать кейс слабой областью
MIN_ATTEMPTS = 2


def get_weak_areas(user_id: int, scenario: str) -> list:
    # какие темы у пользователя в просаде
    data = _load_errors()
    user_data = data.get(str(user_id), {})
    scenario_data = user_data.get(scenario, {})

    weak_areas = []
    for case_id, stats in scenario_data.items():
        if stats["attempts"] >= MIN_ATTEMPTS:
            avg_score = stats["total_score"] / stats["attempts"]
            if avg_score < 7:  # Средний балл ниже 7 — слабая область
                weak_areas.append({
                    "case_id": case_id,
                    "avg_score": avg_score,
                    "attempts": stats["attempts"],
                })

    # сортирую по баллу — худшие темы первыми
    weak_areas.sort(key=lambda x: x["avg_score"])
    return weak_areas


def get_user_stats(user_id: int, scenario: str | None = None) -> dict:
    # статистика по ошибкам
    data = _load_errors()
    user_data = data.get(str(user_id), {})

    if scenario:
        return user_data.get(scenario, {})

    # Общая статистика
    total_cases = 0
    total_attempts = 0
    total_score = 0

    for scenario_data in user_data.values():
        for case_stats in scenario_data.values():
            total_cases += 1
            total_attempts += case_stats["attempts"]
            total_score += case_stats["total_score"]

    avg_score = total_score / total_attempts if total_attempts > 0 else 0

    return {
        "total_cases": total_cases,
        "total_attempts": total_attempts,
        "avg_score": round(avg_score, 1),
        "scenarios": list(user_data.keys()),
    }


SCENARIO_NAMES = {
    "university": "выбор вуза",
    "job": "поиск работы",
    "adaptation": "адаптация в компании",
}

# ключи кнопок сценариев — по ним получаем название на языке юзера
SCENARIO_KEYS = {
    "university": "btn_university",
    "job": "btn_job",
    "adaptation": "btn_adaptation",
}


def _scenario_name(scenario: str, lang: str) -> str:
    # название сценария на языке юзера
    key = SCENARIO_KEYS.get(scenario)
    if key and lang != "ru":
        return t(key, lang)
    return SCENARIO_NAMES.get(scenario, scenario)


def get_clarifying_question(user_id: int, scenario: str, lang: str = "ru") -> str | None:
    # уточняющий вопрос по самой слабой теме — в следующих сессиях бот ковыряет её глубже
    weak_areas = get_weak_areas(user_id, scenario)
    if not weak_areas:
        return None
    area = weak_areas[0]
    friendly = _scenario_name(scenario, lang)
    return t("adaptive_clarify_question", lang,
             friendly=friendly, case_id=area.get("case_id", ""), score=area["avg_score"])


def get_recommendations(user_id: int, scenario: str, lang: str = "ru") -> list:
    # советы по слабым зонам
    weak_areas = get_weak_areas(user_id, scenario)
    friendly = _scenario_name(scenario, lang)

    recommendations = []
    for area in weak_areas[:3]:
        case_id = area.get("case_id", "unknown")
        recommendations.append(
            t("adaptive_recommendation", lang, case_id=case_id, friendly=friendly, score=area['avg_score'])
        )

    if not recommendations:
        recommendations.append(t("adaptive_no_weak", lang))

    return recommendations

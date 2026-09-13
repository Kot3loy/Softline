"""Адаптивное обучение — отслеживание ошибок и персонализация заданий."""

import logging
import json
import tempfile
import os
from bot.config import config

logger = logging.getLogger(__name__)

# Файл для хранения данных об ошибках
ERRORS_FILE = config.DATA_DIR / "learning_errors.json"


def _load_errors() -> dict:
    """Загрузить данные об ошибках"""
    if ERRORS_FILE.exists():
        try:
            with open(ERRORS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки данных об ошибках: {e}")
    return {}


def _save_errors(data: dict):
    """Сохранить данные об ошибках (атомарная запись — write-to-temp-then-rename)"""
    try:
        ERRORS_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Пишем во временный файл, потом делаем rename — не потеряем данные при краше
        fd, tmp_path = tempfile.mkstemp(dir=ERRORS_FILE.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # Атомарная замена (на Windows os.replace тоже атомарен для одного volume)
            os.replace(tmp_path, str(ERRORS_FILE))
        except Exception:
            # Если что-то пошло не так — удаляем временный файл
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
    except Exception as e:
        logger.error(f"Ошибка сохранения данных об ошибках: {e}")


def record_error(user_id: int, case_id: str, scenario: str, score: int):
    """Записать ошибку пользователя"""
    data = _load_errors()

    if str(user_id) not in data:
        data[str(user_id)] = {}

    user_data = data[str(user_id)]
    if scenario not in user_data:
        user_data[scenario] = {}

    # Обновляем статистику по кейсу
    if case_id not in user_data[scenario]:
        user_data[scenario][case_id] = {
            "attempts": 0,
            "total_score": 0,
            "errors": [],
        }

    case_stats = user_data[scenario][case_id]
    case_stats["attempts"] += 1
    case_stats["total_score"] += score

    # Если оценка низкая (< 6), добавляем в список ошибок
    if score < 6:
        case_stats["errors"].append({
            "score": score,
            "attempt": case_stats["attempts"],
        })

    _save_errors(data)
    logger.info(f"Записана ошибка: user={user_id}, case={case_id}, score={score}")


def get_weak_areas(user_id: int, scenario: str) -> list:
    """Получить слабые области пользователя"""
    data = _load_errors()
    user_data = data.get(str(user_id), {})
    scenario_data = user_data.get(scenario, {})

    weak_areas = []
    for case_id, stats in scenario_data.items():
        if stats["attempts"] > 0:
            avg_score = stats["total_score"] / stats["attempts"]
            if avg_score < 7:  # Средний балл ниже 7 — слабая область
                weak_areas.append({
                    "case_id": case_id,
                    "avg_score": avg_score,
                    "attempts": stats["attempts"],
                })

    # Сортируем по среднему баллу (худшие первыми)
    weak_areas.sort(key=lambda x: x["avg_score"])
    return weak_areas


def get_user_stats(user_id: int, scenario: str = None) -> dict:
    """Получить статистику пользователя"""
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


def get_recommendations(user_id: int, scenario: str) -> list:
    """Получить рекомендации для улучшения"""
    weak_areas = get_weak_areas(user_id, scenario)
    friendly = SCENARIO_NAMES.get(scenario, scenario)

    recommendations = []
    for area in weak_areas[:3]:
        case_id = area.get("case_id", "неизвестно")
        recommendations.append(
            f"Задание «{case_id}» ({friendly}) — средний балл {area['avg_score']:.1f}, повтори его"
        )

    if not recommendations:
        recommendations.append("Отлично! У тебя нет слабых областей в этом сценарии.")

    return recommendations

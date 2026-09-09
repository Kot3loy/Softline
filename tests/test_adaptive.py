import pytest
import asyncio
from bot.core.adaptive import record_error, get_weak_areas, get_user_stats, get_recommendations


def test_record_error():
    """Тест записи ошибки"""
    # Уникальный тестовый пользователь чтобы не конфликтовать с предыдущими запусками
    test_uid = 999999999
    record_error(test_uid, "test_case_1", "university", 5)
    record_error(test_uid, "test_case_1", "university", 8)
    record_error(test_uid, "test_case_2", "university", 4)

    # Проверяем что данные записались
    stats = get_user_stats(test_uid, "university")
    assert "test_case_1" in stats
    assert stats["test_case_1"]["attempts"] >= 2


def test_get_weak_areas():
    """Тест получения слабых областей"""
    test_uid = 999999999
    record_error(test_uid, "weak_case", "university", 3)
    weak = get_weak_areas(test_uid, "university")
    assert len(weak) > 0


def test_get_recommendations():
    """Тест получения рекомендаций"""
    test_uid = 999999999
    record_error(test_uid, "rec_case", "university", 2)
    recs = get_recommendations(test_uid, "university")
    assert len(recs) > 0

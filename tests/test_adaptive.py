import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from bot.core.adaptive import record_error, get_weak_areas, get_user_stats, get_recommendations


@pytest.fixture
def tmp_errors_file(tmp_path):
    """Временный файл для тестов чтобы не засорять production"""
    test_file = tmp_path / "test_errors.json"
    test_file.write_text("{}", encoding="utf-8")
    with patch("bot.core.adaptive.ERRORS_FILE", test_file):
        yield test_file


def test_record_error(tmp_errors_file):
    """Тест записи ошибки"""
    test_uid = 888888888
    record_error(test_uid, "test_case_1", "university", 5)
    record_error(test_uid, "test_case_1", "university", 8)
    record_error(test_uid, "test_case_2", "university", 4)

    # Проверяем что данные записались
    stats = get_user_stats(test_uid, "university")
    assert "test_case_1" in stats
    assert stats["test_case_1"]["attempts"] >= 2


def test_get_weak_areas(tmp_errors_file):
    """Тест получения слабых областей"""
    test_uid = 888888888
    record_error(test_uid, "weak_case", "university", 3)
    weak = get_weak_areas(test_uid, "university")
    assert len(weak) > 0


def test_get_recommendations(tmp_errors_file):
    """Тест получения рекомендаций"""
    test_uid = 888888888
    record_error(test_uid, "rec_case", "university", 2)
    recs = get_recommendations(test_uid, "university")
    assert len(recs) > 0

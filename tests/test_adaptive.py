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
    record_error(test_uid, "weak_case", "university", 4)
    weak = get_weak_areas(test_uid, "university")
    assert len(weak) > 0


def test_single_attempt_not_weak(tmp_errors_file):
    """Одна неудачная попытка — ещё не слабая область"""
    test_uid = 888888889
    record_error(test_uid, "solo_case", "university", 3)
    weak = get_weak_areas(test_uid, "university")
    assert all(w["case_id"] != "solo_case" for w in weak)


def test_two_low_attempts_weak(tmp_errors_file):
    """Две попытки с низким средним — слабая область"""
    test_uid = 888888890
    record_error(test_uid, "bad_case", "job", 4)
    record_error(test_uid, "bad_case", "job", 5)
    weak = get_weak_areas(test_uid, "job")
    assert any(w["case_id"] == "bad_case" for w in weak)


def test_two_good_attempts_not_weak(tmp_errors_file):
    """Две попытки с хорошим средним — не слабая область"""
    test_uid = 888888891
    record_error(test_uid, "good_case", "adaptation", 8)
    record_error(test_uid, "good_case", "adaptation", 9)
    weak = get_weak_areas(test_uid, "adaptation")
    assert all(w["case_id"] != "good_case" for w in weak)


def test_get_recommendations(tmp_errors_file):
    """Тест получения рекомендаций"""
    test_uid = 888888888
    record_error(test_uid, "rec_case", "university", 2)
    record_error(test_uid, "rec_case", "university", 3)
    recs = get_recommendations(test_uid, "university")
    assert len(recs) > 0

"""Тесты переводов — RAG-ключи, fallback, полнота STRINGS."""

import pytest

from bot.translations import STRINGS, t


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_rag_keys_return_real_strings(lang):
    for key in ("rag_relevant_info", "rag_use_context", "rag_no_context"):
        val = t(key, lang)
        assert isinstance(val, str)
        assert val != key
        assert len(val) > 10


def test_rag_keys_differ_between_languages():
    for key in ("rag_relevant_info", "rag_use_context", "rag_no_context"):
        assert t(key, "ru") != t(key, "en")


def test_missing_key_returns_key_itself():
    assert t("no_such_key_xyz") == "no_such_key_xyz"
    assert t("no_such_key_xyz", "en") == "no_such_key_xyz"


def test_invalid_lang_falls_back_to_ru():
    assert t("btn_back", "de") == t("btn_back", "ru")


def test_kwargs_formatting():
    val = t("exam_avg", "ru", n=7)
    assert "7" in val
    assert "{n}" not in val


def test_kwargs_missing_does_not_raise():
    val = t("exam_avg", "ru")
    assert isinstance(val, str)
    assert "{n}" in val


@pytest.mark.parametrize("key", sorted(STRINGS))
def test_all_strings_keys_return_str_both_langs(key):
    assert key in STRINGS
    for lang in ("ru", "en"):
        val = t(key, lang)
        assert isinstance(val, str), f"{key}/{lang} not str"
        assert val != "", f"{key}/{lang} empty"

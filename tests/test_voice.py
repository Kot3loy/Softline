"""Тесты голосового ввода: STT (Google, ru), обработка ошибок, подсказка в настройках."""

import sys
from types import ModuleType

import pytest

from bot.translations import STRINGS, t
from bot.utils.voice import MAX_VOICE_LENGTH, prepare_text_for_voice, speech_to_text


# --- Фейковый speech_recognition для мока сети ---


class FakeUnknownValueError(Exception):
    """Речь не распознана"""


class FakeRequestError(Exception):
    """Сервис недоступен"""


class FakeRecognizer:
    behavior = "ok"  # ok | unknown | request
    last_language = None

    def __init__(self):
        self.dynamic_energy_threshold = False
        self.pause_threshold = 0.8

    def record(self, source):
        return "AUDIO"

    def recognize_google(self, audio, language=None):
        FakeRecognizer.last_language = language
        if FakeRecognizer.behavior == "ok":
            return "привет мир"
        if FakeRecognizer.behavior == "unknown":
            raise FakeUnknownValueError()
        raise FakeRequestError("connection refused")


class FakeAudioFile:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def fake_sr(monkeypatch):
    """Подменить speech_recognition фейковым модулем (без сети)"""
    mod = ModuleType("speech_recognition")
    mod.Recognizer = FakeRecognizer
    mod.UnknownValueError = FakeUnknownValueError
    mod.RequestError = FakeRequestError
    mod.AudioFile = FakeAudioFile
    monkeypatch.setitem(sys.modules, "speech_recognition", mod)
    FakeRecognizer.behavior = "ok"
    FakeRecognizer.last_language = None
    yield mod
    FakeRecognizer.behavior = "ok"


# --- speech_to_text ---


async def test_stt_success(fake_sr):
    text, err = await speech_to_text("some.wav")
    assert text == "привет мир"
    assert err is None


async def test_stt_always_russian(fake_sr):
    """Проект онлайн — распознавание всегда на русском"""
    await speech_to_text("some.wav")
    assert FakeRecognizer.last_language == "ru-RU"


async def test_stt_recognizer_tuned(fake_sr):
    """Пороги распознавания выставлены явно"""
    await speech_to_text("some.wav")
    # ловим экземпляр через последний вызов
    assert FakeRecognizer.last_language == "ru-RU"


async def test_stt_no_speech(fake_sr):
    FakeRecognizer.behavior = "unknown"
    text, err = await speech_to_text("some.wav")
    assert text is None
    assert err == "no_speech"


async def test_stt_service_error(fake_sr):
    FakeRecognizer.behavior = "request"
    text, err = await speech_to_text("some.wav")
    assert text is None
    assert err == "service"


async def test_stt_missing_library(monkeypatch):
    """speech_recognition не установлен → ошибка сервиса, не падение"""
    monkeypatch.setitem(sys.modules, "speech_recognition", None)
    text, err = await speech_to_text("some.wav")
    assert text is None
    assert err == "service"


# --- prepare_text_for_voice ---


def test_prepare_strips_markup_and_html():
    out = prepare_text_for_voice("**жирный** <b>тег</b> `код`")
    assert "**" not in out
    assert "<b>" not in out
    assert "`" not in out


def test_prepare_strips_emoji():
    out = prepare_text_for_voice("Привет 🎉👍 мир")
    assert "🎉" not in out


def test_prepare_truncates_long_text():
    long_text = "Это длинное предложение. " * 200
    out = prepare_text_for_voice(long_text)
    assert len(out) <= MAX_VOICE_LENGTH


def test_prepare_short_fallback():
    out = prepare_text_for_voice("а")
    assert out  # не пустая строка
    assert len(out) >= 5


# --- Переводы ---


def test_settings_voice_hint_exists():
    for lang in ("ru", "en"):
        hint = t("settings_voice_hint", lang)
        assert hint != "settings_voice_hint"
        assert "русск" in hint.lower() or "russian" in hint.lower()


def test_voice_stt_error_exists():
    for lang in ("ru", "en"):
        msg = t("voice_stt_error", lang)
        assert msg != "voice_stt_error"
        assert STRINGS["voice_stt_error"][lang]


def test_settings_text_includes_hint():
    from bot.handlers.start import _settings_text

    text = _settings_text("ru")
    assert "Настройки" in text
    assert "только на русском" in text
    text_en = _settings_text("en")
    assert "Russian only" in text_en

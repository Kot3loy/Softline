"""Тесты голосового ввода: STT (Google, ru), обработка ошибок, подсказка в настройках."""

import sys
from types import ModuleType

import pytest

from bot.translations import STRINGS, t
from bot.utils.voice import (
    MAX_VOICE_LENGTH,
    prepare_text_for_voice,
    speech_to_text,
    stt_language_for,
)


# --- Фейковый speech_recognition для мока сети ---


class FakeUnknownValueError(Exception):
    """Речь не распознана"""


class FakeRequestError(Exception):
    """Сервис недоступен"""


class FakeRecognizer:
    behavior = "ok"  # ok | unknown | request | request_then_ok
    last_language = None
    calls = 0
    threads = []

    def __init__(self):
        self.dynamic_energy_threshold = False
        self.pause_threshold = 0.8

    def record(self, source):
        return "AUDIO"

    def recognize_google(self, audio, language=None):
        import threading
        FakeRecognizer.last_language = language
        FakeRecognizer.calls += 1
        FakeRecognizer.threads.append(threading.current_thread())
        if FakeRecognizer.behavior == "ok":
            return "привет мир"
        if FakeRecognizer.behavior == "unknown":
            raise FakeUnknownValueError()
        if FakeRecognizer.behavior == "request_then_ok" and FakeRecognizer.calls > 1:
            return "со второй попытки"
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
    monkeypatch.setattr("bot.utils.voice.STT_RETRY_DELAY", 0, raising=False)
    FakeRecognizer.behavior = "ok"
    FakeRecognizer.last_language = None
    FakeRecognizer.calls = 0
    FakeRecognizer.threads = []
    yield mod
    FakeRecognizer.behavior = "ok"


# --- speech_to_text ---


async def test_stt_success(fake_sr):
    text, err = await speech_to_text("some.wav")
    assert text == "привет мир"
    assert err is None


async def test_stt_runs_off_event_loop(fake_sr):
    """Сетевое распознавание не должно блокировать event loop"""
    import threading

    await speech_to_text("some.wav")

    assert FakeRecognizer.threads
    assert all(thread is not threading.main_thread() for thread in FakeRecognizer.threads)


async def test_stt_default_language_is_russian(fake_sr):
    """По умолчанию распознаём на русском"""
    await speech_to_text("some.wav")
    assert FakeRecognizer.last_language == "ru-RU"


async def test_stt_explicit_language_is_respected(fake_sr):
    """Язык можно передать — для англоязычного интерфейса"""
    await speech_to_text("some.wav", language="en-US")
    assert FakeRecognizer.last_language == "en-US"


async def test_stt_retries_after_service_error(fake_sr):
    """Сервис моргнул — пробуем ещё раз, прежде чем сдаться"""
    FakeRecognizer.behavior = "request_then_ok"
    text, err = await speech_to_text("some.wav")
    assert text == "со второй попытки"
    assert err is None
    assert FakeRecognizer.calls == 2


def test_stt_language_mapping():
    assert stt_language_for("ru") == "ru-RU"
    assert stt_language_for("en") == "en-US"
    assert stt_language_for("") == "ru-RU"


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


def test_settings_voice_hint_mentions_always_accepted():
    # голосовые принимаем всегда, озвучка — только при включённом голосе
    ru = t("settings_voice_hint", "ru").lower()
    assert "всегда" in ru
    assert "голос" in ru


def test_voice_stt_error_exists():
    for lang in ("ru", "en"):
        msg = t("voice_stt_error", lang)
        assert msg != "voice_stt_error"
        assert STRINGS["voice_stt_error"][lang]


def test_settings_text_includes_hint():
    from bot.handlers.start import _settings_text

    text = _settings_text("ru")
    assert "Настройки" in text
    assert "русский" in text
    text_en = _settings_text("en")
    assert "Russian" in text_en

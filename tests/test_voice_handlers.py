"""Голосовые в чате: приём всегда, озвучка только при включённом голосе, подготовка аудио."""

import pytest
from unittest.mock import AsyncMock, patch

from pydub import AudioSegment

from bot.handlers import voice as voice_mod
from bot.handlers.voice import handle_voice, _handle_voice_exam, _convert_to_wav


# --- подготовка аудио для stt ---

def test_convert_to_wav_is_mono_16k(tmp_path):
    src = tmp_path / "in.wav"
    stereo = AudioSegment.silent(duration=500, frame_rate=48000).set_channels(2)
    stereo.export(src, format="wav")

    out = tmp_path / "out.wav"
    _convert_to_wav(str(src), str(out))

    prepared = AudioSegment.from_wav(str(out))
    assert prepared.channels == 1
    assert prepared.frame_rate == 16000


def test_convert_to_wav_trims_long_audio(tmp_path):
    src = tmp_path / "long.wav"
    AudioSegment.silent(duration=(voice_mod.STT_MAX_SECONDS + 5) * 1000).export(src, format="wav")

    out = tmp_path / "out.wav"
    _convert_to_wav(str(src), str(out))

    prepared = AudioSegment.from_wav(str(out))
    assert len(prepared) <= voice_mod.STT_MAX_SECONDS * 1000 + 50


# --- озвучка только при voice_enabled ---

async def _run_voice_info(mock_message, test_db, voice_enabled: int):
    from bot.database.db import get_or_create_user, update_user

    uid = mock_message.from_user.id
    await get_or_create_user(uid)
    await update_user(uid, voice_enabled=voice_enabled)

    with patch.object(voice_mod, "_convert_to_wav", lambda ogg, wav: wav), \
            patch.object(voice_mod, "speech_to_text", AsyncMock(return_value=("как выбрать вуз", None))), \
            patch.object(voice_mod, "answer_info_question", AsyncMock(return_value="Ответ про вуз")), \
            patch.object(voice_mod, "text_to_speech", AsyncMock(return_value="voice.mp3")):
        await handle_voice(mock_message, AsyncMock())


@pytest.mark.asyncio
async def test_voice_always_accepted_text_reply_when_voice_off(mock_message, test_db):
    # голос приняли и распознали, но озвучки нет — голос у юзера выключен
    await _run_voice_info(mock_message, test_db, voice_enabled=0)

    mock_message.answer_voice.assert_not_awaited()
    mock_message.answer.assert_awaited()
    assert "Ответ про вуз" in mock_message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_voice_reply_only_when_enabled(mock_message, test_db):
    await _run_voice_info(mock_message, test_db, voice_enabled=1)

    mock_message.answer_voice.assert_awaited_once()


# --- экзаменатор: голос — ответ на задание ---

@pytest.mark.asyncio
async def test_voice_exam_replies_with_voice_when_enabled(mock_message, test_db, monkeypatch):
    from bot.database.db import get_or_create_user, update_user
    from bot.handlers import examiner

    uid = mock_message.from_user.id
    await get_or_create_user(uid)
    await update_user(uid, voice_enabled=1)

    async def fake_exam_answer(fake_msg, state):
        await fake_msg.answer("📊 Оценка: 7/10\n\nХороший ответ")

    with patch.object(voice_mod, "_convert_to_wav", lambda ogg, wav: wav), \
            patch.object(voice_mod, "speech_to_text", AsyncMock(return_value=("мой ответ", None))), \
            patch.object(voice_mod, "text_to_speech", AsyncMock(return_value="voice.mp3")), \
            patch.object(examiner, "handle_exam_answer", side_effect=fake_exam_answer):
        state = AsyncMock()
        await _handle_voice_exam(mock_message, state)

    mock_message.answer_voice.assert_awaited_once()


@pytest.mark.asyncio
async def test_voice_exam_no_voice_when_disabled(mock_message, test_db):
    from bot.database.db import get_or_create_user, update_user
    from bot.handlers import examiner

    uid = mock_message.from_user.id
    await get_or_create_user(uid)
    await update_user(uid, voice_enabled=0)

    async def fake_exam_answer(fake_msg, state):
        await fake_msg.answer("📊 Оценка: 7/10")

    with patch.object(voice_mod, "_convert_to_wav", lambda ogg, wav: wav), \
            patch.object(voice_mod, "speech_to_text", AsyncMock(return_value=("мой ответ", None))), \
            patch.object(voice_mod, "text_to_speech", AsyncMock(return_value="voice.mp3")), \
            patch.object(examiner, "handle_exam_answer", side_effect=fake_exam_answer):
        state = AsyncMock()
        await _handle_voice_exam(mock_message, state)

    mock_message.answer_voice.assert_not_awaited()


@pytest.mark.asyncio
async def test_voice_exam_uses_user_language_for_stt(mock_message, test_db):
    from bot.database.db import get_or_create_user, update_user
    from bot.handlers import examiner

    uid = mock_message.from_user.id
    await get_or_create_user(uid)
    await update_user(uid, voice_enabled=0, language="en")

    async def fake_exam_answer(fake_msg, state):
        await fake_msg.answer("feedback")

    stt = AsyncMock(return_value=("my answer", None))
    with patch.object(voice_mod, "_convert_to_wav", lambda ogg, wav: wav), \
            patch.object(voice_mod, "speech_to_text", stt), \
            patch.object(examiner, "handle_exam_answer", side_effect=fake_exam_answer):
        await _handle_voice_exam(mock_message, AsyncMock())

    # англоязычному юзеру распознаём английскую речь
    assert stt.await_args.args[1] == "en-US"

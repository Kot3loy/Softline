"""Хендлер голосовых сообщений — STT, TTS, переключение голосового режима."""

import logging
import tempfile
import os
import shutil
from dataclasses import dataclass
from aiogram import Router, F
from aiogram.types import Message, FSInputFile, Chat, User
from aiogram.fsm.context import FSMContext

_log = logging.getLogger(__name__)

# Optional voice dependencies
try:
    from pydub import AudioSegment
    _VOICE_AVAILABLE = True
except ImportError:
    _VOICE_AVAILABLE = False
    AudioSegment = None

if not _VOICE_AVAILABLE:
    _log.warning("Voice features disabled: pydub not available (audioop missing in Python 3.14+)")

# Skip ffmpeg setup if voice not available
if _VOICE_AVAILABLE:
    _ffmpeg_path = shutil.which("ffmpeg")
    _ffprobe_path = shutil.which("ffprobe")

    if not _ffmpeg_path:
        for p in [r"C:\ffmpeg\bin", r"C:\Program Files\ffmpeg\bin", "/usr/bin", "/usr/local/bin"]:
            if os.path.exists(os.path.join(p, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")):
                _ffmpeg_path = os.path.join(p, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
                break

    if not _ffprobe_path and _ffmpeg_path:
        _ffprobe_path = os.path.join(
            os.path.dirname(_ffmpeg_path),
            "ffprobe.exe" if os.name == "nt" else "ffprobe"
        )
        if not os.path.exists(_ffprobe_path):
            _ffprobe_path = None

    if _ffmpeg_path:
        AudioSegment.converter = _ffmpeg_path
        _log.info(f"ffmpeg: {_ffmpeg_path}")
    if _ffprobe_path:
        AudioSegment.probe = _ffprobe_path
        _log.info(f"ffprobe: {_ffprobe_path}")
    if not _ffmpeg_path:
        _log.warning("ffmpeg не найден — голосовые сообщения не будут работать")
else:
    _ffmpeg_path = None
    _ffprobe_path = None

from bot.translations import t
from bot.utils.voice import speech_to_text, text_to_speech
from bot.utils.lang import get_lang
from bot.core.scenarios import answer_info_question
from bot.database.db import get_or_create_user

router = Router()


@dataclass
class VoiceMessage:
    """Обёртка для голосового сообщения, совместимая с handle_exam_answer"""
    text: str
    from_user: User
    chat: Chat
    bot: object

    async def answer(self, text: str, **kwargs):
        return await self.bot.send_message(self.chat.id, text, **kwargs)

    async def answer_voice(self, *args, **kwargs):
        pass


@router.message(F.voice)
async def handle_voice(msg: Message, state: FSMContext):
    """Обработка голосовых сообщений"""
    current_state = await state.get_state()

    if current_state and "ExamState" in str(current_state):
        await _handle_voice_exam(msg, state)
        return

    user_id = msg.from_user.id

    if not _VOICE_AVAILABLE:
        user_data = await get_or_create_user(user_id)
        lang = get_lang(user_data)
        await msg.answer(t("voice_error", lang))
        return

    tmp_dir = tempfile.mkdtemp()
    try:
        file = await msg.bot.get_file(msg.voice.file_id)
        file_path = file.file_path

        tmp_file = os.path.join(tmp_dir, "voice.ogg")
        await msg.bot.download_file(file_path, tmp_file)

        wav_file = os.path.join(tmp_dir, "voice.wav")
        try:
            audio = AudioSegment.from_ogg(tmp_file)
            audio.export(wav_file, format="wav")
        except Exception as e:
            _log.warning(f"Ошибка конвертации аудио: {e}")
            try:
                import speech_recognition as sr
                recognizer = sr.Recognizer()
                with sr.AudioFile(tmp_file) as source:
                    audio = recognizer.record(source)
                text = recognizer.recognize_google(audio, language="ru-RU")
                wav_file = None
            except Exception:
                user_data = await get_or_create_user(user_id)
                lang = get_lang(user_data)
                await msg.answer(t("voice_error", lang))
                return

        await msg.bot.send_chat_action(msg.chat.id, "typing")
        if wav_file:
            text = await speech_to_text(wav_file)

        if not text:
            user_data = await get_or_create_user(user_id)
            lang = get_lang(user_data)
            await msg.answer(t("voice_no_speech", lang))
            return

        user_data = await get_or_create_user(user_id)
        scenario = user_data.get("current_scenario", "university")
        lang = get_lang(user_data)

        answer = await answer_info_question(text, scenario, user_id=user_id, lang=lang)

        # Переводим ответ если язык не русский
        if lang != "ru":
            from bot.utils.translator import translate_text
            answer = await translate_text(answer, target_lang=lang)

        voice_file = await text_to_speech(answer)

        if voice_file:
            try:
                await msg.answer_voice(FSInputFile(voice_file))
                await msg.answer(t("voice_text_prefix", lang, text=answer), parse_mode="HTML")
            finally:
                if os.path.exists(voice_file):
                    os.remove(voice_file)
        else:
            await msg.answer(answer, parse_mode="HTML")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def _handle_voice_exam(msg: Message, state: FSMContext):
    """Обработка голосового сообщения в режиме экзаменатора"""
    from bot.handlers.examiner import handle_exam_answer

    if not _VOICE_AVAILABLE:
        user_data = await get_or_create_user(msg.from_user.id)
        lang = get_lang(user_data)
        await msg.answer(t("voice_error", lang))
        return

    tmp_dir = tempfile.mkdtemp()

    try:
        tmp_file = os.path.join(tmp_dir, "voice.ogg")

        file = await msg.bot.get_file(msg.voice.file_id)
        await msg.bot.download_file(file.file_path, tmp_file)

        wav_file = os.path.join(tmp_dir, "voice.wav")
        try:
            audio = AudioSegment.from_ogg(tmp_file)
            audio.export(wav_file, format="wav")
        except Exception:
            user_data = await get_or_create_user(msg.from_user.id)
            lang = get_lang(user_data)
            await msg.answer(t("voice_error", lang))
            return

        text = await speech_to_text(wav_file)

        if not text:
            user_data = await get_or_create_user(msg.from_user.id)
            lang = get_lang(user_data)
            await msg.answer(t("voice_no_speech", lang))
            return

        fake_msg = VoiceMessage(
            text=text,
            from_user=msg.from_user,
            chat=msg.chat,
            bot=msg.bot,
        )
        await handle_exam_answer(fake_msg, state)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

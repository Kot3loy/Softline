"""Хендлер голосовых сообщений — STT, TTS, переключение голосового режима."""

import logging
import tempfile
import os
import shutil
from dataclasses import dataclass
from aiogram import Router, F
from aiogram.types import Message, FSInputFile, Chat, User
from aiogram.fsm.context import FSMContext

from pydub import AudioSegment

_log = logging.getLogger(__name__)

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

from bot.utils.voice import speech_to_text, text_to_speech
from bot.core.scenarios import answer_info_question
from bot.database.db import get_or_create_user

router = Router()
logger = logging.getLogger(__name__)


@dataclass
class VoiceMessage:
    """Обёртка для голосового сообщения, совместимая с handle_exam_answer"""
    text: str
    from_user: User
    chat: Chat
    bot: object
    _answered: bool = False

    async def answer(self, text: str, **kwargs):
        self._answered = True
        return await self.bot.send_message(self.chat.id, text, **kwargs)

    async def answer_voice(self, *args, **kwargs):
        pass


@router.message(F.voice)
async def handle_voice(msg: Message, state: FSMContext):
    """Обработка голосовых сообщений"""
    from bot.handlers.examiner import ExamState
    current_state = await state.get_state()

    if current_state and "ExamState" in str(current_state):
        await _handle_voice_exam(msg, state)
        return

    user_id = msg.from_user.id
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
            logger.warning(f"Ошибка конвертации аудио: {e}")
            try:
                import speech_recognition as sr
                recognizer = sr.Recognizer()
                with sr.AudioFile(tmp_file) as source:
                    audio = recognizer.record(source)
                text = recognizer.recognize_google(audio, language="ru-RU")
                wav_file = None
            except Exception:
                await msg.answer(
                    "🎤 Не удалось обработать голосовое сообщение.\n"
                    "Напиши текстом — я обязательно отвечу!"
                )
                return

        await msg.bot.send_chat_action(msg.chat.id, "typing")
        if wav_file:
            text = await speech_to_text(wav_file)
        else:
            text = None

        if not text:
            await msg.answer(
                "🎤 Не удалось распознать речь.\n"
                "Попробуй говорить чётче или напиши текстом."
            )
            return

        user_data = await get_or_create_user(user_id)
        scenario = user_data.get("current_scenario", "university")

        answer = await answer_info_question(text, scenario, user_id=user_id)

        voice_file = await text_to_speech(answer)

        if voice_file:
            try:
                await msg.answer_voice(FSInputFile(voice_file))
                await msg.answer(f"📝 <b>Текст:</b>\n{answer}", parse_mode="HTML")
            finally:
                os.remove(voice_file)
        else:
            await msg.answer(answer, parse_mode="HTML")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def _handle_voice_exam(msg: Message, state: FSMContext):
    """Обработка голосового сообщения в режиме экзаменатора"""
    from bot.handlers.examiner import handle_exam_answer

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
            await msg.answer("🎤 Не удалось обработать голос. Попробуй текстом.")
            return

        text = await speech_to_text(wav_file)

        if not text:
            await msg.answer("🎤 Не распознал речь. Попробуй ещё раз или напиши текстом.")
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

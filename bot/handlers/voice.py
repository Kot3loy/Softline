# голосовые сообщения: распознаю (stt), потом отвечаю и озвучиваю (tts)

import logging
import tempfile
import os
import shutil
from dataclasses import dataclass, field
from aiogram import Router, F
from aiogram.types import Message, FSInputFile, Chat, User
from aiogram.fsm.context import FSMContext

_log = logging.getLogger(__name__)

# Опциональные зависимости для голоса
try:
    from pydub import AudioSegment
    _VOICE_AVAILABLE = True
except ImportError:
    _VOICE_AVAILABLE = False
    AudioSegment = None

if not _VOICE_AVAILABLE:
    _log.warning("Voice features disabled: pydub not available (audioop missing in Python 3.14+)")

# Настройка ffmpeg, если голосовые функции активны
if _VOICE_AVAILABLE:
    _ffmpeg_path = shutil.which("ffmpeg")
    _ffprobe_path = shutil.which("ffprobe")

    if not _ffmpeg_path:
        for p in [r"C:\ffmpeg\bin", r"C:\Program Files\ffmpeg\bin", "/usr/bin", "/usr/local/bin",
                  os.path.join(os.getcwd(), "bin")]:
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
from bot.utils.voice import speech_to_text, text_to_speech, stt_language_for
from bot.utils.lang import get_lang
from bot.core.scenarios import answer_info_question
from bot.database.db import get_or_create_user

router = Router()

# google stt точнее всего на mono 16 кГц и не принимает записи длиннее минуты
STT_SAMPLE_RATE = 16000
STT_MAX_SECONDS = 60


def _convert_to_wav(ogg_path: str, wav_path: str) -> str:
    # ogg из телеграма → mono 16 кГц wav: так распознавание заметно точнее
    audio = AudioSegment.from_ogg(ogg_path)
    if len(audio) > STT_MAX_SECONDS * 1000:
        audio = audio[: STT_MAX_SECONDS * 1000]
    audio = audio.set_channels(1).set_frame_rate(STT_SAMPLE_RATE)
    try:
        audio = audio.normalize()
    except Exception:
        pass
    audio.export(wav_path, format="wav")
    return wav_path


@dataclass
class VoiceMessage:
    # обёртка под голосовое: handle_exam_answer ждёт обычный msg с .text
    text: str
    from_user: User
    chat: Chat
    bot: object
    sent_texts: list = field(default_factory=list)

    async def answer(self, text: str, **kwargs):
        self.sent_texts.append(text)
        return await self.bot.send_message(self.chat.id, text, **kwargs)

    async def answer_voice(self, *args, **kwargs):
        pass


@router.message(F.voice)
async def handle_voice(msg: Message, state: FSMContext):
    # юзер скинул голосовое — распознаю и отвечу (в экзаменаторе как ответ на задание)
    current_state = await state.get_state()

    if current_state and "ExamState" in str(current_state):
        await _handle_voice_exam(msg, state)
        return

    user_id = msg.from_user.id

    user_data = await get_or_create_user(user_id)
    lang = get_lang(user_data)

    if not _VOICE_AVAILABLE:
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
            _convert_to_wav(tmp_file, wav_file)
        except Exception as e:
            # Без ffmpeg конвертация не удалась — дальше идти некуда
            _log.warning(f"Ошибка конвертации аудио: {e}")
            await msg.answer(t("voice_error", lang))
            return

        await msg.bot.send_chat_action(msg.chat.id, "typing")
        text, stt_error = await speech_to_text(wav_file, stt_language_for(lang))

        if not text:
            key = "voice_stt_error" if stt_error == "service" else "voice_no_speech"
            await msg.answer(t(key, lang))
            return

        scenario = user_data.get("current_scenario", "university")

        answer = await answer_info_question(text, scenario, user_id=user_id, lang=lang)

        # если юзер не на русском — перевожу ответ
        if lang != "ru":
            from bot.utils.translator import translate_text
            answer = await translate_text(answer, target_lang=lang)

        from bot.handlers.info import _should_show_disclaimer
        disclaimer = t("disclaimer", lang) if _should_show_disclaimer(answer) else ""

        # озвучка только если юзер сам включил голосовые ответы
        voice_enabled = user_data.get("voice_enabled", 0) == 1
        voice_file = await text_to_speech(answer) if voice_enabled else None

        if voice_file:
            try:
                await msg.answer_voice(FSInputFile(voice_file))
                sent = await msg.answer(t("voice_text_prefix", lang, text=answer) + disclaimer, parse_mode="HTML")
                try:
                    from bot.handlers.start import _remember
                    _remember(msg.chat.id, getattr(sent, "message_id", None))
                except Exception:
                    pass
            finally:
                if os.path.exists(voice_file):
                    os.remove(voice_file)
        else:
            sent = await msg.answer(answer + disclaimer, parse_mode="HTML")
            try:
                from bot.handlers.start import _remember
                _remember(msg.chat.id, getattr(sent, "message_id", None))
            except Exception:
                pass

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def _handle_voice_exam(msg: Message, state: FSMContext):
    # голос как ответ на задание
    from bot.handlers.examiner import handle_exam_answer

    user_data = await get_or_create_user(msg.from_user.id)
    lang = get_lang(user_data)

    if not _VOICE_AVAILABLE:
        await msg.answer(t("voice_error", lang))
        return

    tmp_dir = tempfile.mkdtemp()

    try:
        tmp_file = os.path.join(tmp_dir, "voice.ogg")

        file = await msg.bot.get_file(msg.voice.file_id)
        await msg.bot.download_file(file.file_path, tmp_file)

        wav_file = os.path.join(tmp_dir, "voice.wav")
        try:
            _convert_to_wav(tmp_file, wav_file)
        except Exception:
            await msg.answer(t("voice_error", lang))
            return

        text, stt_error = await speech_to_text(wav_file, stt_language_for(lang))

        if not text:
            key = "voice_stt_error" if stt_error == "service" else "voice_no_speech"
            await msg.answer(t(key, lang))
            return

        fake_msg = VoiceMessage(
            text=text,
            from_user=msg.from_user,
            chat=msg.chat,
            bot=msg.bot,
        )
        await handle_exam_answer(fake_msg, state)

        # озвучка разбора — только если юзер включил голосовые ответы
        if user_data.get("voice_enabled", 0) == 1 and fake_msg.sent_texts:
            feedback_text = fake_msg.sent_texts[0]
            voice_file = await text_to_speech(feedback_text)
            if voice_file:
                try:
                    await msg.answer_voice(FSInputFile(voice_file))
                finally:
                    if os.path.exists(voice_file):
                        os.remove(voice_file)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

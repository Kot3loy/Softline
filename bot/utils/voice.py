"""Модуль голоса — преобразование текста в речь (edge-tts) и речи в текст (SpeechRecognition)."""

import logging
import re
import tempfile
import os

logger = logging.getLogger(__name__)

MAX_VOICE_LENGTH = 1500

# Русские нейронные голоса Microsoft (м/ж)
VOICE_MALE = "ru-RU-DmitryNeural"
VOICE_FEMALE = "ru-RU-SvetlanaNeural"


def prepare_text_for_voice(text: str) -> str:
    """Очистить текст от markdown/HTML/эмодзи для озвучки"""
    if not text:
        return ""

    t = text

    # Убираем HTML-теги
    t = re.sub(r'<[^>]+>', '', t)

    # Убираем markdown-форматирование
    t = re.sub(r'\*\*([^*]+)\*\*', r'\1', t)
    t = re.sub(r'\*([^*]+)\*', r'\1', t)
    t = re.sub(r'__([^_]+)__', r'\1', t)
    t = re.sub(r'_([^_]+)_', r'\1', t)
    t = re.sub(r'~~([^~]+)~~', r'\1', t)
    t = re.sub(r'`([^`]+)`', r'\1', t)

    # Убираем ссылки [текст](url) → текст
    t = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', t)

    # Убираем эмодзи
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"
        "\u3030"
        "]+",
        flags=re.UNICODE,
    )
    t = emoji_pattern.sub('', t)

    # Убираем буллеты и нумерацию
    t = re.sub(r'^[\s]*[•\-\*]\s*', '', t, flags=re.MULTILINE)
    t = re.sub(r'^[\s]*\d+\.\s*', '', t, flags=re.MULTILINE)

    # Убираем заголовки секций (строки ЗАГЛАВНЫМИ или с двоеточием)
    t = re.sub(r'^[А-ЯA-Z][А-ЯA-Z\s]{3,}:?\s*$', '', t, flags=re.MULTILINE)

    # Заменяем тире на запятую
    t = re.sub(r'\s*[-—]\s*', ', ', t)

    # Убираем лишние пробелы и переносы
    t = re.sub(r'\n{2,}', '. ', t)
    t = re.sub(r'\n', ' ', t)
    t = re.sub(r'\s{2,}', ' ', t)

    # Обрезаем если слишком длинно
    if len(t) > MAX_VOICE_LENGTH:
        cut = t[:MAX_VOICE_LENGTH]
        last_dot = cut.rfind('.')
        if last_dot > MAX_VOICE_LENGTH // 2:
            t = cut[:last_dot + 1]
        else:
            t = cut + '.'

    t = t.strip()

    if not t or len(t) < 5:
        return "Вот мой ответ. Подробности в текстовом сообщении."

    return t


async def text_to_speech(text: str, lang: str = "ru", voice: str = None) -> str:
    """Преобразовать текст в голосовое сообщение через edge-tts (нейронные голоса)"""
    clean_text = prepare_text_for_voice(text)
    voice = voice or VOICE_MALE

    # старый вариант с gTTS — медленный и голос ужасный, но работает как фоллбэк
    # from gtts import gTTS
    # tts = gTTS(text=clean_text, lang='ru')
    # tts.save("temp.mp3")
    # return "temp.mp3"

    try:
        import edge_tts
        import asyncio

        tmp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp_file.name
        tmp_file.close()

        communicate = edge_tts.Communicate(clean_text, voice)
        await communicate.save(tmp_path)

        logger.info(f"Голос сгенерирован (edge-tts, {voice}): {len(clean_text)} символов")
        return tmp_path

    except Exception as e:
        logger.error(f"Ошибка edge-tts: {e}")
        # Fallback на gTTS если edge-tts не работает
        try:
            from gtts import gTTS
            loop = asyncio.get_running_loop()

            def _generate():
                tts = gTTS(text=clean_text, lang=lang, slow=False)
                tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                tts.save(tmp.name)
                return tmp.name

            file_path = await loop.run_in_executor(None, _generate)
            logger.info(f"Голос сгенерирован (gTTS fallback): {file_path}")
            return file_path

        except Exception as e2:
            logger.error(f"Ошибка gTTS fallback: {e2}")
            return None


async def speech_to_text(audio_file_path: str) -> str:
    """Преобразовать голосовое сообщение в текст (SpeechRecognition)"""
    try:
        import speech_recognition as sr

        recognizer = sr.Recognizer()

        with sr.AudioFile(audio_file_path) as source:
            audio = recognizer.record(source)

        text = recognizer.recognize_google(audio, language="ru-RU")
        logger.info(f"Распознан текст: {text[:100]}...")
        return text

    except sr.UnknownValueError:
        logger.warning("Не удалось распознать речь")
        return None

    except sr.RequestError as e:
        logger.error(f"Ошибка сервиса распознавания: {e}")
        return None

    except Exception as e:
        logger.error(f"Ошибка распознавания: {e}")
        return None

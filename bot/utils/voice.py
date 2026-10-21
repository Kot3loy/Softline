# голос: текст -> речь (edge-tts), речь -> текст (Google STT через SpeechRecognition)

import logging
import re
import tempfile
import os
import asyncio

logger = logging.getLogger(__name__)

MAX_VOICE_LENGTH = 1500

# языки распознавания google stt (русский по умолчанию — проект русскоязычный)
STT_LANGUAGE_RU = "ru-RU"
STT_LANGUAGE_EN = "en-US"
STT_RETRIES = 2
STT_RETRY_DELAY = 1.0


def stt_language_for(lang: str) -> str:
    # язык интерфейса → язык распознавания речи
    if (lang or "").lower().startswith("en"):
        return STT_LANGUAGE_EN
    return STT_LANGUAGE_RU

# Русские нейронные голоса Microsoft (мужской/женский)
VOICE_MALE = "ru-RU-DmitryNeural"
VOICE_FEMALE = "ru-RU-SvetlanaNeural"


def prepare_text_for_voice(text: str) -> str:
    # tts не умеет читать эмодзи и *, тут просто вычищаю текст
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


async def text_to_speech(text: str, lang: str = "ru", voice: str | None = None) -> str | None:
    # превращаю текст в голосовое сообщение, сначала пробую edge-tts, если он лег — гтts
    clean_text = prepare_text_for_voice(text)
    voice = voice or VOICE_MALE

    try:
        import edge_tts

        tmp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp_file.name
        tmp_file.close()

        try:
            communicate = edge_tts.Communicate(clean_text, voice)
            await communicate.save(tmp_path)
            logger.info(f"Голос сгенерирован (edge-tts, {voice}): {len(clean_text)} символов")
            return tmp_path
        except Exception as e:
            logger.error(f"Ошибка edge-tts: {e}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    except Exception as e:
        logger.error(f"Ошибка edge-tts: {e}")
        # Fallback на gTTS если edge-tts не работает
        try:
            from gtts import gTTS
            loop = asyncio.get_running_loop()

            def _generate():
                tts = gTTS(text=clean_text, lang=lang, slow=False)
                tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                tmp_path = tmp.name
                tmp.close()
                tts.save(tmp_path)
                return tmp_path

            file_path = await loop.run_in_executor(None, _generate)
            logger.info(f"Голос сгенерирован (gTTS fallback): {file_path}")
            return file_path

        except Exception as e2:
            logger.error(f"Ошибка gTTS fallback: {e2}")
            return None


def _recognize_sync(sr, audio_file_path: str, language: str) -> str:
    # сетевое распознавание синхронное: вызываем его из отдельного потока
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.6  # чуть быстрее резать конец фразы
    recognizer.energy_threshold = 250  # тихую запись тоже распознаём
    try:
        recognizer.operation_timeout = 20
    except Exception:
        pass

    with sr.AudioFile(audio_file_path) as source:
        audio = recognizer.record(source)

    return recognizer.recognize_google(audio, language=language)


async def speech_to_text(audio_file_path: str, language: str = STT_LANGUAGE_RU) -> tuple:
    # распознаю wav в текст через google stt
    # возвращает (текст, тип_ошибки): ("привет", None) — ок, (None, "service") — сервис лёг
    try:
        import speech_recognition as sr
    except ImportError:
        logger.error("speech_recognition не установлен. Установи: pip install SpeechRecognition")
        return None, "service"

    # сервис может моргнуть — делаем пару попыток, прежде чем сдаться
    for attempt in range(STT_RETRIES):
        try:
            text = await asyncio.to_thread(_recognize_sync, sr, audio_file_path, language)
            logger.info(f"Распознан текст ({language}): {text[:100]}...")
            return text, None

        except sr.UnknownValueError:
            # сервис ответил, но речь не разобрал — повторять бессмысленно
            logger.info("STT: речь не распознана")
            return None, "no_speech"

        except sr.RequestError as e:
            # нет связи с google stt — одна повторная попытка
            logger.warning(f"STT: сервис недоступен (попытка {attempt + 1}): {e}")
            if attempt < STT_RETRIES - 1:
                await asyncio.sleep(STT_RETRY_DELAY)

        except Exception as e:
            logger.warning(f"Ошибка распознавания: {e}")
            return None, "service"

    return None, "service"

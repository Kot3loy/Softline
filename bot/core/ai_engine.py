"""AI-движок — генерация заданий, оценка ответов, работа с GigaChat API."""

import logging
import json
import re
import time
import asyncio
from gigachat import GigaChatAsyncClient
from gigachat.models import ChatCompletionRequest, ChatMessage, ChatModelOptions
from bot.config import config

logger = logging.getLogger(__name__)


def _strip_markdown(text: str) -> str:
    """Убрать markdown-разметку из текста AI"""
    if not text:
        return text
    # Заголовки ## / ### / ####
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Жирный **text** и __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    # Курсив *text* и _text_ (осторожно, не трогать односимвольные)
    text = re.sub(r'\*{2,}(.+?)\*{2,}', r'\1', text)
    # Горизонтальные линии ---
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
    # Списки - item или * item
    text = re.sub(r'^[\s]*[-*]\s+', '• ', text, flags=re.MULTILINE)
    # Убрать пустые строки подряд (макс 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

_client = None
_client_lock = asyncio.Lock()

_last_responses = {}
MAX_HISTORY = 3

_last_responses_ttl = {}
RESPONSES_TTL = 3600

_cleanup_counter = 0
_CLEANUP_INTERVAL = 50

MAX_RETRIES = 3
RETRY_DELAY = 2

_ERROR_MARKERS = (
    "Извини", "Не удалось", "Слишком много", "ошибка",
    "Ошибка", "не могу", "Попробуй позже",
    "Sorry", "Failed", "Too many", "error", "Error",
    "can't", "Try again later",
)


def _sanitize_input(text: str) -> str:
    """Санитизация пользовательского ввода — защита от prompt injection"""
    if not text:
        return ""

    # Обрезаем до разумной длины
    text = text[:2000]

    # Убираем потенциально опасные инструкции
    dangerous_patterns = [
        r'ignore\s+(all\s+)?previous\s+instructions',
        r'ignore\s+all\s+prior',
        r'disregard\s+(all\s+)?instructions',
        r'you\s+are\s+now',
        r'new\s+instructions:',
        r'system\s*:\s*',
        r'assistant\s*:\s*',
        # Русские паттерны
        r'игнорируй\s+(вс[её]\s+)?предыдущие\s+инструкции',
        r'забудь\s+(вс[её]\s+)?инструкции',
        r'ты\s+теперь',
        r'новые\s+инструкции:',
        r'прими\s+во\s+внимание\s+что',
        r'в\s+качестве\s+системы',
    ]
    for pattern in dangerous_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    return text.strip()


def _cleanup_old_data():
    """Очистить устаревшие данные"""
    now = time.time()
    expired_users = [uid for uid, t in _last_responses_ttl.items() if now - t > RESPONSES_TTL]
    for uid in expired_users:
        _last_responses.pop(uid, None)
        _last_responses_ttl.pop(uid, None)


async def _get_client():
    """Ленивая инициализация GigaChat async-клиента"""
    global _client
    async with _client_lock:
        if _client is None:
            logger.info("Инициализация GigaChat клиента...")
            _client = GigaChatAsyncClient(
                credentials=config.GIGACHAT_CREDENTIALS,
                model=config.GIGACHAT_MODEL,
                verify_ssl_certs=config.GIGACHAT_VERIFY_SSL_CERTS,
                timeout=90,
                max_retries=3,
                retry_backoff_factor=2,
            )
            await _client.__aenter__()
            logger.info("GigaChat клиент готов")
        return _client


def _save_response(user_id: int, response: str):
    """Сохранить ответ в историю"""
    if user_id not in _last_responses:
        _last_responses[user_id] = []
    _last_responses[user_id].append(response[:500])
    if len(_last_responses[user_id]) > MAX_HISTORY:
        _last_responses[user_id] = _last_responses[user_id][-MAX_HISTORY:]
    _last_responses_ttl[user_id] = time.time()


def _parse_json(text: str, default: dict) -> dict:
    """Парсинг JSON из ответа AI (может быть в markdown code blocks)"""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\s*\n?', '', text)
        text = re.sub(r'\n?```\s*$', '', text)
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Пытаемся найти JSON — сначала простой (без вложенности), потом весь до конца
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        # Попытка 2: вложенный JSON — берём от первой { до последней }
        first = text.find('{')
        last = text.rfind('}')
        if first != -1 and last > first:
            try:
                return json.loads(text[first:last + 1])
            except json.JSONDecodeError:
                pass
        return default


def _parse_text_response(text: str, case_type: str) -> dict:
    """Парсинг текстового ответа GigaChat когда JSON не вернулся"""
    lines = text.strip().split("\n")

    situation = ""
    question = ""
    options = []
    correct = 0
    hint = ""

    for line in lines:
        line = line.strip()
        if line.startswith("Ситуация:") or line.startswith("СITUАЦИЯ:"):
            situation = line.split(":", 1)[1].strip()
        elif line.startswith("Вопрос:") or line.startswith("ВОПРОС:"):
            question = line.split(":", 1)[1].strip()
        elif re.match(r'^[A-D]\.\s', line):
            options.append(line[3:].strip())
        elif "правильный ответ" in line.lower():
            parts = line.split(":", 1)
            letter = parts[1].strip().upper() if len(parts) > 1 else ""
            if letter in "ABCD":
                correct = ord(letter) - ord("A")
        elif line.startswith("Объяснение:") or line.startswith("ПОДСКАЗКА:"):
            hint = line.split(":", 1)[1].strip()

    if not situation:
        return {}

    result = {
        "type": case_type,
        "situation": situation,
        "question": question,
        "hint": hint,
    }

    if case_type == "choice":
        result["options"] = options if len(options) == 4 else ["Вариант A", "Вариант B", "Вариант C", "Вариант D"]
        result["correct"] = correct
        result["explanation"] = hint
    else:
        result["good_answer_points"] = []
        result["common_mistakes"] = []

    return result


async def ask_ai(prompt: str, system_prompt: str = "", max_tokens: int = 700, strip_md: bool = False) -> str:
    """Отправить запрос к AI через GigaChat с retry"""

    messages = []
    if system_prompt:
        messages.append(ChatMessage(role="system", content=system_prompt))
    messages.append(ChatMessage(role="user", content=prompt))

    model_options = ChatModelOptions(max_tokens=max_tokens) if max_tokens else None

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            client = await _get_client()
            chat = ChatCompletionRequest(messages=messages, model_options=model_options)
            response = await asyncio.wait_for(client.achat.create(chat), timeout=60)
            raw = response.messages[0].content[0].text
            if raw and raw.strip():
                logger.debug(f"GigaChat response: {raw[:500]}")
                return _strip_markdown(raw) if strip_md else raw
            # Пустой ответ — повторяем
            logger.warning(f"GigaChat вернул пустой ответ (попытка {attempt + 1}/{MAX_RETRIES})")
            last_error = "пустой ответ"
        except asyncio.TimeoutError:
            logger.error(f"GigaChat API timeout (попытка {attempt + 1}/{MAX_RETRIES})")
            last_error = "timeout"
        except Exception as e:
            logger.error(f"Ошибка AI (попытка {attempt + 1}/{MAX_RETRIES}): {e}")
            last_error = str(e)

        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(RETRY_DELAY * (attempt + 1))

    logger.error(f"GigaChat не ответил после {MAX_RETRIES} попыток: {last_error}")
    return "Извини, AI сейчас перегружен. Попробуй через минуту."


async def generate_case(scenario: str, difficulty: str = "medium", weak_areas: list = None, case_type: str = "open") -> dict:
    """Сгенерировать задание для экзаменатора с retry"""
    global _cleanup_counter
    _cleanup_counter += 1
    if _cleanup_counter % _CLEANUP_INTERVAL == 0:
        _cleanup_old_data()

    weak_hint = ""
    if weak_areas:
        weak_list = ", ".join([w.get("case_id", "") for w in weak_areas[:3]])
        weak_hint = f"\n\nСфокусируйся на слабых областях пользователя: {weak_list}."

    if case_type == "choice":
        system = (
            "Ты — наставник для новичков. Генерируешь мини-тесты.\n\n"
            "СТИЛЬ:\n"
            "- Ситуация — 1-2 предложения, живым языком.\n"
            "- Используй имена: Аня, Дима, Катя, Саша.\n"
            "- Конкретика: должности, цифры, названия.\n"
            f"{weak_hint}\n\n"
            "ВАРИАНТЫ:\n"
            "- Ровно 4 штуки (A, B, C, D)\n"
            "- Один правильный, три — правдоподобные ловушки\n"
            "- Примерно одной длины\n"
            "- Без 'Все вышеперечисленное'\n\n"
            "НЕ ПОВТОРЯЙСЯ. Формат: короткая история + конкретный вопрос."
        )
        prompt = (
            f"Сгенерируй 1 мини-тест для сценария '{scenario}'.\n\n"
            "Примеры (НЕ копируй):\n"
            "- Аня на собеседовании в Яндексе. HR: 'ЗП 80К, но через полгода пересмотр'. "
            "Аня хочет 100К. Что ответить?\n"
            "- Дима пришёл стажёром. Начальник кричит на него при коллегах. Как поступить?\n\n"
            "JSON:\n"
            '{\n'
            '  "type": "choice",\n'
            '  "situation": "Живая ситуация 1-2 предложения",\n'
            '  "question": "Конкретный вопрос",\n'
            '  "options": ["A", "B", "C", "D"],\n'
            '  "correct": 0,\n'
            '  "hint": "Подсказка",\n'
            '  "explanation": "Почему этот ответ (1 предложение)"\n'
            '}'
        )
    else:
        system = (
            "Ты — наставник для новичков. Генерируешь мини-кейсы.\n\n"
            "СТИЛЬ:\n"
            "- Ситуация — 1-2 предложения, живым языком.\n"
            "- Используй имена: Аня, Дима, Катя, Саша.\n"
            "- Конкретика: должности, цифры, названия.\n"
            "- Каждый кейс — отдельная история.\n"
            "- Меняй формат: диалог, письмо, ситуация, дилемма.\n"
            f"{weak_hint}\n\n"
            "ЧЕРЕДУЙ:\n"
            "- Отрасли: IT, маркетинг, продажи, HR, финансы\n"
            "- Форматы: 'Что ответить?', 'Как поступить?', 'Разбери ошибку'\n"
            "- Сложность: бытовые → стратегические\n\n"
            "НЕ ПОВТОРЯЙСЯ. Формат: короткая история + конкретный вопрос."
        )
        prompt = (
            f"Сгенерируй 1 мини-кейс для сценария '{scenario}'.\n\n"
            "Примеры (НЕ копируй):\n"
            "- Ты 2 недели на новой работе. Начальник в отпуске. "
            "Коллега: 'Этот отчёт делается по-другому, но я занят'. Что делаешь?\n"
            "- На собеседовании предлагают ЗП на 30% меньше ожиданий, "
            "но обещают рост. Твой ход.\n\n"
            "JSON:\n"
            '{\n'
            '  "type": "open",\n'
            '  "situation": "Живая ситуация 1-2 предложения",\n'
            '  "question": "Конкретный вопрос",\n'
            '  "hint": "Подсказка",\n'
            '  "good_answer_points": ["очка 1", "очка 2"],\n'
            '  "common_mistakes": ["ошибка 1"]\n'
            '}'
        )

    # Retry: до 3 попыток с упрощающим промптом
    fallback_prompt = (
        f"Сгенерируй задание для сценария '{scenario}'. "
        'Верни ТОЛЬКО JSON без markdown: {{"type": "{case_type}", "situation": "...", "question": "..."}}'
    )
    prompts = [prompt, fallback_prompt, fallback_prompt]

    for attempt in range(MAX_RETRIES):
        result = await ask_ai(prompts[attempt], system)

        # Если ask_ai вернул ошибку — повторяем
        if any(result.startswith(m) for m in _ERROR_MARKERS):
            logger.warning(f"generate_case: ошибка от AI (попытка {attempt + 1}): {result[:100]}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
            continue

        parsed = _parse_json(result, {})
        if not parsed or parsed.get("situation") == "Не удалось сгенерировать задание":
            parsed = _parse_text_response(result, case_type)
        if parsed and parsed.get("situation"):
            if "type" not in parsed:
                parsed["type"] = case_type
            if parsed["type"] == "choice":
                if "options" not in parsed or not isinstance(parsed["options"], list):
                    parsed["type"] = "open"
                elif len(parsed["options"]) != 4:
                    parsed["type"] = "open"
                elif "correct" not in parsed:
                    parsed["correct"] = 0
            return parsed

        logger.warning(f"generate_case: невалидный JSON (попытка {attempt + 1})")
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(RETRY_DELAY)

    # Все попытки исчерпаны
    logger.error(f"generate_case: не удалось после {MAX_RETRIES} попыток для {scenario}")
    return {
        "type": case_type,
        "situation": "Не удалось сгенерировать задание",
        "question": "Попробуй позже — AI сейчас перегружен",
    }


async def evaluate_answer(user_answer: str, case_data: dict) -> dict:
    """Оценить ответ пользователя на задание с retry"""
    global _cleanup_counter
    _cleanup_counter += 1
    if _cleanup_counter % _CLEANUP_INTERVAL == 0:
        _cleanup_old_data()

    # Санитизация ввода
    user_answer = _sanitize_input(user_answer)

    system = (
        "Ты — практикующий наставник, оцениваешь ответ на задание. "
        "Пиши как опытный коллега, который даёт обратную связь.\n\n"
        "ШКАЛА ОЦЕНКИ (будь мягче):\n"
        "0-2: ТОЛЬКО абсурд, шутки, одно слово, не по теме\n"
        "3-4: Ответ пытается помочь, но слишком коротко\n"
        "5-6: По делу, есть суть\n"
        "7-8: Хорошо, есть конкретные шаги\n"
        "9-10: Отлично, лучше ожиданий\n"
        "Правило: если человек ПЫТАЕТСЯ ответить по теме — минимум 3 балла.\n\n"
        "При оценивании СРАВНИВАЙ ответ с реальными примерами из базы знаний. "
        "Если ответ похож на типичную ошибку — мягко подскажи как лучше. "
        "Если ответ хороший — приведи пример из практики.\n\n"
        "СТИЛЬ (Stop Slop — анти-AI правила):\n"
        "- Feedback короткий: 3-4 предложения, один абзац.\n"
        "- НЕ начинай с 'Хороший ответ!', 'Отлично!', 'Интересный подход'. Просто оцени.\n"
        "- НЕ пиши 'Стоит отметить', 'Важно учитывать', 'Необходимо обратить внимание'.\n"
        "- НЕ используй бинарные контрасты: 'Не X, а Y'. Просто скажи Y.\n"
        "- НЕ повторяй вопрос перед ответом.\n"
        "- Конкретика: 'Добавь цифры в резюме' вместо 'Подойдите к этому серьёзно'.\n"
        "- strengths и weaknesses — максимум 2 пункта, коротко.\n"
        "- example_answer — 2-3 предложения. source — название.\n"
        "- Пиши ОДНИМ абзацем, без списков. Как будто пишешь другу.\n"
        "- Отвечай СПЛОШНЫМ текстом без форматирования. НЕ используй markdown: заголовки (##, ####), разделители (---), жирный (**), списки. Просто текст."
    )
    prompt = (
        f"Задание: {case_data.get('situation', '')}\n"
        f"Вопрос: {case_data.get('question', '')}\n\n"
        f"Ответ человека:\n{user_answer}\n\n"
        f"Очки хорошего ответа: {case_data.get('good_answer_points', [])}\n\n"
        "Оцени (0-10) и дай обратную связь: feedback одним абзацем (3-4 предложения). "
        "strengths/weaknesses максимум 2 пункта. example 2-3 предложения.\n\n"
        "JSON:\n"
        '{\n'
        '  "score": 7,\n'
        '  "feedback": "Обратная связь одним абзацем — что хорошо, что лучше, пример из практики",\n'
        '  "strengths": ["что сделал хорошо"],\n'
        '  "weaknesses": ["что можно улучшить"],\n'
        '  "example_answer": "Конкретный пример хорошего ответа (2-3 предложения)",\n'
        '  "source": "Название источника или статьи"\n'
        '}'
    )

    fallback_prompt = (
        f"Задание: {case_data.get('situation', '')}\n"
        f"Вопрос: {case_data.get('question', '')}\n"
        f"Ответ: {user_answer}\n\n"
        'Оцени 0-10. Верни ТОЛЬКО JSON без markdown: {{"score": 7, "feedback": "..."}}'
    )
    prompts = [prompt, fallback_prompt, fallback_prompt]

    for attempt in range(MAX_RETRIES):
        result = await ask_ai(prompts[attempt], system, max_tokens=600)

        if any(result.startswith(m) for m in _ERROR_MARKERS):
            logger.warning(f"evaluate_answer: ошибка от AI (попытка {attempt + 1})")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
            continue

        parsed = _parse_json(result, {
            "score": 5,
            "feedback": "Не удалось оценить ответ",
            "strengths": [],
            "weaknesses": [],
            "recommendations": [],
            "example_answer": "",
            "source": "",
        })

        # Гарантируем что score — число в диапазоне [0, 10]
        if isinstance(parsed.get("score"), (int, float)):
            parsed["score"] = max(0, min(10, int(parsed["score"])))
            # Успешно получили валидный ответ
            if "feedback" in parsed and isinstance(parsed["feedback"], str):
                parsed["feedback"] = parsed["feedback"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            return parsed

        logger.warning(f"evaluate_answer: невалидный score (попытка {attempt + 1})")
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(RETRY_DELAY)

    # Все попытки исчерпаны
    logger.error(f"evaluate_answer: не удалось после {MAX_RETRIES} попыток")
    return {
        "score": 5,
        "feedback": "AI сейчас перегружен — оценка приблизительная. Попробуй позже для точной обратной связи.",
        "strengths": [],
        "weaknesses": [],
        "recommendations": [],
        "example_answer": "",
        "source": "",
    }

"""AI-движок — генерация заданий, оценка ответов, работа с GigaChat API.
написал когда разобрался как GigaChat API работает, до этого долго мучился
с OpenRouter но он платный оказался"""

import logging
import json
import re
import time
import asyncio
from gigachat import GigaChatAsyncClient
from gigachat.models import ChatCompletionRequest, ChatMessage
from bot.config import config

logger = logging.getLogger(__name__)

_client = None
_client_lock = asyncio.Lock()

# Хранилище последних ответов
_last_responses = {}  # type: dict[int, list[str]]
MAX_HISTORY = 3

# Rate limiting: 5 запросов в минуту на пользователя
_rate_limits = {}  # type: dict[int, list[float]]
RATE_LIMIT = 5
RATE_WINDOW = 60  # секунд

# Время жизни _last_responses — 1 час
_last_responses_ttl = {}  # type: dict[int, float]
RESPONSES_TTL = 3600

# Счётчик вызовов для периодической очистки
_cleanup_counter = 0
_CLEANUP_INTERVAL = 50  # каждые 50 запросов


def _check_rate_limit(user_id: int) -> bool:
    """Проверить rate limit для пользователя. True = можно, False = слишком часто"""
    now = time.time()
    if user_id not in _rate_limits:
        _rate_limits[user_id] = []

    # Убираем старые записи
    _rate_limits[user_id] = [t for t in _rate_limits[user_id] if now - t < RATE_WINDOW]

    if len(_rate_limits[user_id]) >= RATE_LIMIT:
        return False

    _rate_limits[user_id].append(now)
    return True


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
    """Очистить устаревшие данные (вызывать периодически)"""
    now = time.time()

    # Очистка _last_responses
    expired_users = [uid for uid, t in _last_responses_ttl.items() if now - t > RESPONSES_TTL]
    for uid in expired_users:
        _last_responses.pop(uid, None)
        _last_responses_ttl.pop(uid, None)

    # Очистка rate limits
    expired_rates = [uid for uid, times in _rate_limits.items()
                     if not times or now - times[-1] > RATE_WINDOW * 2]
    for uid in expired_rates:
        _rate_limits.pop(uid, None)


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


def _get_recent_responses(user_id: int) -> str:
    """Получить последние ответы пользователя для антиповтора"""
    responses = _last_responses.get(user_id, [])
    if not responses:
        return ""
    return "\n".join(f"- {r[:200]}" for r in responses[-MAX_HISTORY:])


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


async def ask_ai(prompt: str, system_prompt: str = "", max_tokens: int = 2000, user_id: int = None) -> str:
    """Отправить запрос к AI через GigaChat с rate limiting"""
    # Rate limit check
    if user_id and not _check_rate_limit(user_id):
        logger.warning(f"Rate limit exceeded for user {user_id}")
        return "Слишком много запросов. Подожди минуту и попробуй снова."

    messages = []
    if system_prompt:
        messages.append(ChatMessage(role="system", content=system_prompt))
    messages.append(ChatMessage(role="user", content=prompt))

    try:
        client = await _get_client()
        chat = ChatCompletionRequest(messages=messages)
        response = await asyncio.wait_for(client.achat.create(chat), timeout=60)
        raw = response.messages[0].content[0].text
        logger.debug(f"GigaChat response: {raw[:500]}")
        return raw

    except asyncio.TimeoutError:
        logger.error("GigaChat API timeout (60 сек)")
        return "Извини, AI слишком долго думал. Попробуй позже."
    except Exception as e:
        logger.error(f"Ошибка AI: {e}")
        return "Извини, произошла ошибка при обращении к AI. Попробуй позже."


async def generate_case(scenario: str, difficulty: str = "medium", weak_areas: list = None, case_type: str = "open", user_id: int = None) -> dict:
    """Сгенерировать задание для экзаменатора"""
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

    result = await ask_ai(prompt, system, user_id=user_id)

    parsed = _parse_json(result, {})
    if not parsed or parsed.get("situation") == "Не удалось сгенерировать задание":
        parsed = _parse_text_response(result, case_type)
    if not parsed or not parsed.get("situation"):
        parsed = {
            "type": case_type,
            "situation": "Не удалось сгенерировать задание",
            "question": "Попробуй позже",
        }

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


async def evaluate_answer(user_answer: str, case_data: dict, user_id: int = None) -> dict:
    """Оценить ответ пользователя на задание"""
    global _cleanup_counter
    _cleanup_counter += 1
    if _cleanup_counter % _CLEANUP_INTERVAL == 0:
        _cleanup_old_data()

    # Санитизация ввода
    user_answer = _sanitize_input(user_answer)

    system = (
        "Ты — практикующий наставник, оцениваешь ответ на задание. "
        "Пиши как опытный коллега, который даёт обратную связь.\n\n"
        "ШКАЛА ОЦЕНКИ:\n"
        "0-2: Абсурд, шутки, не по теме\n"
        "3-4: Слишком коротко, без сути\n"
        "5-6: По делу, но нет конкретики\n"
        "7-8: Хорошо, есть конкретные шаги\n"
        "9-10: Отлично, лучше ожиданий\n\n"
        "При оценивании СРАВНИВАЙ ответ с реальными примерами из базы знаний. "
        "Если ответ похож на типичную ошибку — мягко подскажи как лучше. "
        "Если ответ хороший — приведи пример из практики.\n\n"
        "СТИЛЬ (Stop Slop — анти-AI правила):\n"
        "- НЕ начинай с 'Хороший ответ!', 'Отлично!', 'Интересный подход'. Просто оцени.\n"
        "- НЕ пиши 'Стоит отметить', 'Важно учитывать', 'Необходимо обратить внимание'.\n"
        "- НЕ используй бинарные контрасты: 'Не X, а Y'. Просто скажи Y.\n"
        "- НЕ повторяй вопрос перед ответом.\n"
        "- Конкретика: 'Добавь цифры в резюме' вместо 'Подойдите к этому серьёзно'.\n"
        "- Пиши ОДНИМ абзацем, без списков. Как будто пишешь другу."
    )
    prompt = (
        f"Задание: {case_data.get('situation', '')}\n"
        f"Вопрос: {case_data.get('question', '')}\n\n"
        f"Ответ человека:\n{user_answer}\n\n"
        f"Очки хорошего ответа: {case_data.get('good_answer_points', [])}\n\n"
        "Оцени (0-10) и дай обратную связь одним абзацем. "
        "Сравни с реальными примерами и укажи источник.\n\n"
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

    result = await ask_ai(prompt, system, user_id=user_id)
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
    if not isinstance(parsed.get("score"), (int, float)):
        parsed["score"] = 5
    parsed["score"] = max(0, min(10, int(parsed["score"])))

    # Экранируем HTML в feedback чтобы не сломать parse_mode
    if "feedback" in parsed and isinstance(parsed["feedback"], str):
        parsed["feedback"] = parsed["feedback"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    return parsed


async def check_answer_relevance(user_answer: str, case_data: dict, user_id: int = None) -> dict:
    """Проверить релевантность ответа"""
    user_answer = _sanitize_input(user_answer)

    system = (
        "Проверь, является ли ответ адекватным ответом на задание.\n\n"
        "НЕ релевантно (relevant=false):\n"
        "- Оскорбления, угрозы, насилие\n"
        "- Абсурд, провокация, шутки вместо ответа\n"
        "- Полностью не связано с заданием\n"
        "- Одно слово без смысла\n\n"
        "Релевантно (relevant=true):\n"
        "- Пытается ответить на вопрос\n"
        "- Есть конкретика или рассуждения\n"
        "- Серьёзный тон\n\n"
        'JSON: {"relevant": true/false, "reason": "коротко почему"}'
    )

    prompt = (
        f"Задание: {case_data.get('situation', '')}\n"
        f"Вопрос: {case_data.get('question', '')}\n\n"
        f"Ответ: {user_answer}\n\n"
        "Это адекватный ответ?"
    )

    result = await ask_ai(prompt, system, user_id=user_id)
    parsed = _parse_json(result, {"relevant": True, "reason": ""})

    if "relevant" not in parsed:
        parsed = {"relevant": True, "reason": ""}

    return parsed

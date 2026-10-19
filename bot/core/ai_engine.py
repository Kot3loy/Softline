# ai-движок — генерация заданий, оценка ответов, работа с gigachat api

import logging
import json
import re
import time
import asyncio
from gigachat import GigaChatAsyncClient
from gigachat.models import ChatCompletionRequest, ChatMessage, ChatModelOptions
from bot.config import config
from bot.core.choice_options import normalize_choice_case
from bot.core.rag import search
from bot.database.db import save_dialog, get_dialog, clear_dialog_history

logger = logging.getLogger(__name__)


# слова которые gigachat иногда подмешивает в ответы
SLANG_WORDS = {"норм", "братан", "чувак", "дружище"}

# RAG-запрос для генерации кейсов по сценарию (ТЗ этап 2: кейсы на основе базы знаний)
_SCENARIO_RAG_QUERY = {
    "university": "выбор вуза поступление ЕГЭ подводные камни",
    "job": "собеседование резюме стажировка первая работа",
    "adaptation": "адаптация первый рабочий день коллеги начальник",
    "lead": "лидерство делегирование обратная связь команда",
}

def strip_slang(text: str) -> str:
    if not text:
        return text
    result = text
    for word in SLANG_WORDS:
        pattern = r'\b' + re.escape(word) + r'\b'
        result = re.sub(pattern, " ", result, flags=re.IGNORECASE)
    result = re.sub(r'[ \t]+([.,!?;:])', r'\1', result)
    result = re.sub(r'([.,!?;:])\s+([.,!?;:])', r'\1\2', result)
    result = re.sub(r'[ \t]+', ' ', result)
    return result.strip()

def _strip_markdown(text: str) -> str:
    # gigachat любит жирный и заголовки, тут я это вычищаю
    if not text:
        return text
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'\*{2,}(.+?)\*{2,}', r'\1', text)
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*[-*]\s+', '• ', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

_client: "GigaChatAsyncClient | None" = None
_client_lock = asyncio.Lock()

# память диалога инфо-режима: последние пары вопрос-ответ
_sessions: dict[int, list[dict]] = {}
MAX_TURNS = 4

_sessions_ttl: dict[int, float] = {}
SESSIONS_TTL = 3600

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
    # чистим ввод пользователя — защита от prompt injection
    if not text:
        return ""

    # обрезаю до разумной длины
    text = text[:2000]

    # убираю опасные инструкции типа "ignore all previous instructions"
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
    # чистим старые сессии (неактивны больше часа)
    now = time.time()
    expired_users = [uid for uid, ts in _sessions_ttl.items() if now - ts > SESSIONS_TTL]
    for uid in expired_users:
        _sessions.pop(uid, None)
        _sessions_ttl.pop(uid, None)


async def _get_client():
    # создаю клиента gigachat только когда он нужен (ленивая инициализация)
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


async def get_history(user_id: int) -> list[dict]:
    # история диалога из БД (persist) — теперь запоминает
    if not user_id:
        return []
    try:
        turns = await get_dialog(user_id, MAX_TURNS)
        if turns:
            return turns
    except Exception:
        pass
    return []


async def has_history(user_id: int) -> bool:
    return bool(await get_history(user_id))


async def save_turn(user_id: int, question: str, answer: str):
    # запоминаю пару вопрос-ответ в БД (persist)
    if not user_id:
        return
    try:
        await save_dialog(user_id, (question or "")[:400], (answer or "")[:600])
    except Exception as e:
        logger.warning(f"Не удалось сохранить диалог в БД: {e}")
    turns = _sessions.setdefault(user_id, [])
    turns.append({"question": (question or "")[:400], "answer": (answer or "")[:600]})
    if len(turns) > MAX_TURNS:
        _sessions[user_id] = turns[-MAX_TURNS:]
    _sessions_ttl[user_id] = time.time()


async def clear_history(user_id: int):
    # выход из меню — сессия обрывается: память и БД-диалог сطلыются
    if not user_id:
        return
    _sessions.pop(user_id, None)
    _sessions_ttl.pop(user_id, None)
    try:
        await clear_dialog_history(user_id)
    except Exception as e:
        logger.warning(f"Не удалось очистить диалог в БД: {e}")


def _parse_json(text: str, default: dict) -> dict:
    # парсю json из ответа ai (он иногда прячет его в ```json``` блоках)
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\s*\n?', '', text)
        text = re.sub(r'\n?```\s*$', '', text)
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Ищем JSON: сначала простой вариант (без вложенности), затем весь текст до закрывающей скобки
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        # Попытка 2: вложенный JSON — берём от первой открывающей скобки до последней закрывающей
        first = text.find('{')
        last = text.rfind('}')
        if first != -1 and last > first:
            try:
                return json.loads(text[first:last + 1])
            except json.JSONDecodeError:
                pass
        return default


def _parse_text_response(text: str, case_type: str) -> dict:
    # если ai вернул не json, а просто текст — парсю его по строкам
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
        elif re.match(r'^[A-D][\).]\s*', line):
            options.append(re.sub(r'^[A-D][\).]\s*', '', line).strip())
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
        result["options"] = options
        result["correct"] = correct
        result["explanation"] = hint
        # варианты часто лежат внутри вопроса; заглушки не показываем — тогда это открытый вопрос
        result = normalize_choice_case(result)
        if result["type"] == "open":
            result["good_answer_points"] = []
            result["common_mistakes"] = []
    else:
        result["good_answer_points"] = []
        result["common_mistakes"] = []

    return result


async def ask_ai(prompt: str, system_prompt: str = "", max_tokens: int = 700, strip_md: bool = False) -> str:
    # отправляю запрос к gigachat, 3 попытки при ошибке

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
                text = _strip_markdown(raw) if strip_md else raw
                text = strip_slang(text)
                return text
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


async def generate_case(scenario: str, difficulty: str = "medium", weak_areas: list | None = None, case_type: str = "open") -> dict:
    # генерирую задание для экзаменатора через ai
    global _cleanup_counter
    _cleanup_counter += 1
    if _cleanup_counter % _CLEANUP_INTERVAL == 0:
        _cleanup_old_data()

    # слабые области: темы пользователя, не номера заданий
    topic_hint = ""
    weak_hint = ""
    if weak_areas:
        topics = []
        for w in weak_areas[:3]:
            t_ = (w.get("topic") or "").strip()
            if t_:
                topics.append(t_[:60])
        if topics:
            topic_hint = " Слабые темы пользователя: " + "; ".join(topics) + ". Построй кейсы вокруг них."
        else:
            weak_hint = "\n\nСфокусируйся на областях, которые новичок чаще проваливает."

    # факты из базы знаний — кейс строится вокруг реального подводного камня
    facts_block = ""
    try:
        topic_query = _SCENARIO_RAG_QUERY.get(scenario, scenario)
        rag_docs = await asyncio.to_thread(search, f"{topic_query} {topic_hint}", 3, None)
        seen: set[str] = set()
        facts = []
        for d in rag_docs:
            url = d.metadata.get("source_url")
            url = url or None
            snippet = " ".join(d.page_content.split())[:220]
            if snippet in seen:
                continue
            seen.add(snippet)
            facts.append(f"- {snippet}" + (f" (источник: {url})" if url else ""))
        if facts:
            facts_block = "\n\nФАКТЫ ИЗ БАЗЫ ЗНАНИЙ (построй кейс вокруг одного из них, конкретика важна):\n" + "\n".join(facts) + "\n"
    except Exception as e:
        logger.warning(f"generate_case: RAG недоступен, кейс без факт-базы: {e}")

    if case_type == "choice":
        system = (
            "Ты — наставник для новичков. Генерируешь мини-тесты.\n\n"
            "СТИЛЬ:\n"
            "- Ситуация — 1-2 предложения, живым языком.\n"
            "- Используй имена: Аня, Дима, Катя, Саша.\n"
            "- Конкретика: должности, цифры, названия.\n"
            f"{topic_hint}\n\n"
            f"{facts_block}\n"
            "ВАРИАНТЫ:\n"
            "- Ровно 4 штуки (A, B, C, D)\n"
            "- Один правильный, три — правдоподобные ловушки\n"
            "- options — это сами ответы текстом («420 рублей», «Спросить у менеджера»), НЕ буквы и НЕ «Вариант A»\n"
            "- Не перечисляй варианты внутри question — там только сам вопрос\n"
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
            '  "question": "Конкретный вопрос без вариантов внутри",\n'
            '  "options": ["420 рублей", "360 рублей", "240 рублей", "180 рублей"],\n'
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
            f"{topic_hint}{weak_hint}\n\n"
            f"{facts_block}\n"
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

    # Retry: до 3 попыток с упрощенным промптом (уменьшаем сложность запроса)
    fallback_prompt = (
        f"Сгенерируй задание для сценария '{scenario}'. "
        'Верни ТОЛЬКО JSON без markdown: {{"type": "{case_type}", "situation": "...", "question": "..."}}'
    )
    prompts = [prompt, fallback_prompt, fallback_prompt]

    for attempt in range(MAX_RETRIES):
        result = await ask_ai(prompts[attempt], system)

        # Если AI вернул ошибку — повторяем запрос
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
                # восстанавливаем настоящие варианты (llm кладёт их в вопрос) — иначе открытый вопрос
                parsed = normalize_choice_case(parsed)
                if parsed["type"] == "open":
                    parsed.setdefault("good_answer_points", [])
                    parsed.setdefault("common_mistakes", [])
            return {**parsed, "scenario": scenario}

        logger.warning(f"generate_case: невалидный JSON (попытка {attempt + 1})")
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(RETRY_DELAY)

    # Все попытки исчерпаны
    logger.error(f"generate_case: не удалось после {MAX_RETRIES} попыток для {scenario}")
    return {
        "type": case_type,
        "situation": "Не удалось сгенерировать задание",
        "question": "Попробуй позже — AI сейчас перегружен",
        "scenario": scenario,
    }


_SCORE_PATTERNS = (
    r"оценка\s*[:\-—]?\s*(\d{1,2})",
    r"\b(\d{1,2})\s*(?:/|из)\s*10\b",
    r"\b(\d{1,2})\s*балл",
    r"^\s*(\d{1,2})\s*$",
)

MIN_ANSWER_WORDS = 12


def _parse_score_text(text: str) -> dict | None:
    # ai мог ответить текстом, а не json — вытаскиваем оценку из текста
    if not text:
        return None
    for pattern in _SCORE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if not match:
            continue
        score = int(match.group(1))
        if 0 <= score <= 10:
            return {
                "score": score,
                "feedback": _strip_markdown(text)[:900],
                "strengths": [],
                "weaknesses": [],
                "recommendations": [],
                "example_answer": "",
                "source": "",
            }
    return None


def _vague_answer_feedback() -> dict:
    # ответ из пары слов — объясняем, чего не хватило, вместо молчания
    return {
        "score": 3,
        "feedback": "Ответ вышел общим, без конкретики. Разбери ситуацию по шагам: "
                    "что именно сказала бы Аня, какое действие предприняла и почему.",
        "strengths": [],
        "weaknesses": ["Ответ без конкретных шагов"],
        "recommendations": [],
        "example_answer": "",
        "source": "",
        "sources": [],
    }


async def evaluate_answer(user_answer: str, case_data: dict) -> dict:
    # оцениваю ответ пользователя: ищу релевантные материалы в базе знаний, потом прошусь у ai
    global _cleanup_counter
    _cleanup_counter += 1
    if _cleanup_counter % _CLEANUP_INTERVAL == 0:
        _cleanup_old_data()

    # Санитизация ввода
    user_answer = _sanitize_input(user_answer)

    # RAG контекст: ищем релевантные материалы по сценарию кейса
    scenario = case_data.get("scenario", "university")
    # Маппинг сценария → source_type для RAG
    _SCENARIO_SOURCE = {
        "university": "universities",
        "job": ("companies", "interviews"),
        "adaptation": "cases",
    }
    source_type = _SCENARIO_SOURCE.get(scenario)
    query = f"{case_data.get('situation', '')} {case_data.get('question', '')} {user_answer}"
    rag_docs = await asyncio.to_thread(search, query, 3, source_type)

    context = ""
    if rag_docs:
        # внутри всё в русском, перевод ответа уже в хендлере
        context = "Найденная релевантная информация:\n\n"
        for i, doc in enumerate(rag_docs, 1):
            src = doc.metadata.get("title") or "Материал"
            src_url = doc.metadata.get("source_url")
            content = doc.page_content[:800]
            if src_url:
                context += f"{i}. Источник: {src}\nURL: {src_url}\n{content}\n\n"
            else:
                context += f"{i}. Источник: {src}\n{content}\n\n"

    # реальные ссылки на источники — юзеру отдаём проверяемые URL, а не текст LLM
    real_sources = []
    seen_urls = set()
    for doc in rag_docs:
        url = (doc.metadata.get("source_url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        real_sources.append({"title": doc.metadata.get("title") or "Материал", "url": url})
        if len(real_sources) >= 3:
            break

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
        "При оценивании ОБЯЗАТЕЛЬНО СРАВНИВАЙ ответ с найденной информацией из базы знаний. "
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
        "- example_answer — 2-3 предложения. source — название источника.\n"
        "- Пиши ОДНИМ абзацем, без списков. Как будто пишешь другу.\n"
        "- Отвечай СПЛОШНЫМ текстом без форматирования. НЕ используй markdown: заголовки (##, ####), разделители (---), жирный (**), списки. Просто текст."
    )
    rag_use = "Используй найденную информацию для оценки. Если её недостаточно — опирайся на опыт." if rag_docs else "Релевантной информации в базе нет. Оцени на основе своих знаний или скажи, что не знаешь."
    prompt = (
        f"Задание: {case_data.get('situation', '')}\n"
        f"Вопрос: {case_data.get('question', '')}\n\n"
        f"Ответ человека:\n{user_answer}\n\n"
        f"Очки хорошего ответа: {case_data.get('good_answer_points', [])}\n\n"
        f"{context}"
        f"{rag_use}\n\n"
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

        # разбираем ответ: сначала ждём json, если его нет — пробуем вытащить оценку из текста
        parsed = _parse_json(result, {})
        if not parsed or not isinstance(parsed.get("score"), (int, float)):
            parsed = _parse_score_text(result) or {}

        # Гарантируем, что счет — целое число от 0 до 10
        if isinstance(parsed.get("score"), (int, float)):
            parsed["score"] = max(0, min(10, int(parsed["score"])))
            parsed.setdefault("strengths", [])
            parsed.setdefault("weaknesses", [])
            parsed.setdefault("recommendations", [])
            parsed.setdefault("example_answer", "")
            parsed.setdefault("source", "")
            parsed["sources"] = real_sources
            # Успешно получили валидный ответ
            if "feedback" in parsed and isinstance(parsed["feedback"], str):
                parsed["feedback"] = parsed["feedback"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            return parsed

        logger.warning(f"evaluate_answer: невалидный score (попытка {attempt + 1})")
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(RETRY_DELAY)

    # Все попытки исчерпаны
    logger.error(f"evaluate_answer: не удалось после {MAX_RETRIES} попыток")

    # если ответ совсем короткий — честно скажем, чего не хватило
    if len(user_answer.split()) < MIN_ANSWER_WORDS:
        return _vague_answer_feedback()

    return {
        "score": 5,
        "feedback": "AI сейчас перегружен — оценка приблизительная. Попробуй позже для точной обратной связи.",
        "strengths": [],
        "weaknesses": [],
        "recommendations": [],
        "example_answer": "",
        "source": "",
        "sources": real_sources,
    }

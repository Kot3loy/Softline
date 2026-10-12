# -*- coding: utf-8 -*-
# Info-режим. Пользователь спрашивает — бот ищет в базе и отвечает через GigaChat.
# Простой код. Без воды.

import logging
import asyncio
from bot.translations import t
from bot.core.ai_engine import ask_ai, get_history, save_turn
from bot.core.rag import search
from bot.core.prompt_registry import prompt_registry
from bot.utils.translator import translate_html

logger = logging.getLogger(__name__)

_SCENARIO_TOPICS = {
    "university": "выбор вуза, поступление, ЕГЭ, студенческая жизнь",
    "job": "поиск работы, резюме, собеседования, стажировки, карьера",
    "adaptation": "адаптация на новой работе, коллеги, рабочий этикет",
    "lead": "лидерство, управление командой, принятие решений, стратегическое мышление",
}

# Алиасы обратной совместимости
SYSTEM_PROMPTS = {}
STYLE_RULES = ""


async def _get_prompt(name: str) -> str:
    # текущая версия промпта из реестра
    content = prompt_registry.get_content(name)
    if content is None:
        logger.warning(f"Промпт {name} не найден в реестре")
        return ""
    return content


# Системные промпты для каждого сценария (загружаются из реестра)
async def _get_system_prompts():
    return {
        "university": await _get_prompt("university"),
        "job": await _get_prompt("job"),
        "adaptation": await _get_prompt("adaptation"),
        "lead": await _get_prompt("lead"),
    }


async def answer_info_question(question: str, scenario: str, user_id: int = None, lang: str = "ru") -> str:
    # отвечаем на вопрос: ищем в базе знания, склеиваем контекст, просим ai
    docs = await asyncio.to_thread(search, question, 3, None)

    # из найденного делаем контекст
    context = ""
    if docs:
        context = t("rag_relevant_info", lang) + "\n\n"
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source", "Неизвестно")
            content = doc.page_content[:1000]
            context += f"{i}. Источник: {source}\n{content}\n\n"

    # собираю промпт
    system_prompts = await _get_system_prompts()
    system = system_prompts.get(scenario, await _get_prompt("university"))

    frame = f"Тема: {_SCENARIO_TOPICS.get(scenario, _SCENARIO_TOPICS['university'])}.\nДержись темы; на чужой вопрос вежливо верни к своей. Приветствия — коротко и верни к теме.\n\n"

    # история диалога — чтобы бот помнил о чём уже говорили и не здоровался заново
    history_block = ""
    if user_id:
        turns = await get_history(user_id)
        if turns:
            lines = "\n".join(
                f"Юзер: {turn['question']}\nТы: {turn['answer']}" for turn in turns
            )
            history_block = f"История диалога (это одна сессия, продолжай её):\n{lines}\n\n"

    if context:
        prompt = (
            "{history}{frame}User question: {question}\n\n"
            "{context}\n\n"
            "{rag_use}"
        ).format(
            history=history_block,
            frame=frame,
            question=question,
            context=context,
            rag_use=t("rag_use_context", lang)
        )
    else:
        prompt = (
            "{history}{frame}User question: {question}\n\n"
            "{rag_no}"
        ).format(
            history=history_block,
            frame=frame,
            question=question,
            rag_no=t("rag_no_context", lang)
        )

    answer = await ask_ai(prompt, system, max_tokens=700, strip_md=True)

    # сохраняю пару вопрос-ответ в память сессии
    if user_id:
        await save_turn(user_id, question, answer)

    return answer


async def get_welcome_message(scenario: str, lang: str = "ru") -> str:
    # приветствие при входе в сценарий
    welcome_key = f"welcome_{scenario}"
    welcome_text = await _get_prompt(welcome_key)

    if not welcome_text:
        messages = {
            "university": t("welcome_university", lang),
            "job": t("welcome_job", lang),
            "adaptation": t("welcome_adaptation", lang),
        }
        welcome_text = messages.get(scenario, messages["university"])

    examples_key = f"welcome_{scenario}_examples"
    examples = await _get_prompt(examples_key)

    hint = t("info_ask_hint", lang)
    result = f"{welcome_text}\n\n{hint}"
    if examples:
        result += f"\n\n{examples}"

    # в реестре тексты только на русском — для английского переводим на лету
    if lang != "ru":
        result = await translate_html(result, lang)

    return result


# старые константы SYSTEM_PROMPTS / STYLE_RULES — их кто-то импортирует, не убираю
import yaml
from pathlib import Path

_REGISTRY_PATH = Path(__file__).parent.parent / "prompts" / "registry.yaml"

def _load_prompts_sync():
    # считываем промпты сразу при импорте (для старой структуры SYSTEM_PROMPTS)
    global SYSTEM_PROMPTS, STYLE_RULES
    try:
        with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        
        prompts = data.get("prompts", {})
        SYSTEM_PROMPTS = {}
        for name in ("university", "job", "adaptation", "lead"):
            prompt_data = prompts.get(name, {}).get("versions", [])
            if prompt_data:
                SYSTEM_PROMPTS[name] = prompt_data[0].get("content", "")
        
        # STYLE_RULES — первая часть промпта university до ДИСКЛЕЙМЕР
        uni_content = SYSTEM_PROMPTS.get("university", "")
        STYLE_RULES = uni_content.split("ДИСКЛЕЙМЕР")[0] if "ДИСКЛЕЙМЕР" in uni_content else uni_content
    except Exception as e:
        logger.warning(f"Не удалось загрузить промпты для совместимости: {e}")
        SYSTEM_PROMPTS = {}
        STYLE_RULES = ""


# Загружаем при импорте
_load_prompts_sync()
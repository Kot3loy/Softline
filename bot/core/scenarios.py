# -*- coding: utf-8 -*-
"""Сценарии бота — системные промпты, информационный режим, приветственные сообщения."""

import logging
import asyncio
from bot.translations import t
from bot.core.ai_engine import ask_ai, _save_response
from bot.core.rag import search
from bot.core.prompt_registry import prompt_registry

logger = logging.getLogger(__name__)

# Backward compatibility aliases
SYSTEM_PROMPTS = {}
STYLE_RULES = ""


async def _get_prompt(name: str) -> str:
    """Получить промпт из реестра"""
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
    }


async def answer_info_question(question: str, scenario: str, user_id: int = None, lang: str = "ru") -> str:
    """Ответить на вопрос в информационном режиме (RAG + AI)"""
    # Ищем релевантные документы (sync → async)
    docs = await asyncio.to_thread(search, question, 3, None)

    # Формируем контекст из найденных документов
    context = ""
    if docs:
        context = t("rag_relevant_info", lang) + "\n\n"
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source", "Неизвестно")
            content = doc.page_content[:1000]
            context += f"{i}. Источник: {source}\n{content}\n\n"

    # Формируем промпт
    system_prompts = await _get_system_prompts()
    system = system_prompts.get(scenario, await _get_prompt("university"))

    if context:
        prompt = (
            "User question: {question}\n\n"
            "{context}\n\n"
            "{rag_use}"
        ).format(
            question=question,
            context=context,
            rag_use=t("rag_use_context", lang)
        )
    else:
        prompt = (
            "User question: {question}\n\n"
            "{rag_no}"
        ).format(
            question=question,
            rag_no=t("rag_no_context", lang)
        )

    answer = await ask_ai(prompt, system, max_tokens=700, strip_md=True)

    # Сохраняем ответ в историю для антиповтора
    if user_id:
        _save_response(user_id, answer)

    return answer


async def get_welcome_message(scenario: str, lang: str = "ru") -> str:
    """Приветственное сообщение для сценария"""
    welcome_key = f"welcome_{scenario}"
    welcome_text = await _get_prompt(welcome_key)

    if not welcome_text:
        messages = {
            "university": t("welcome_university", lang),
            "job": t("welcome_job", lang),
            "adaptation": t("welcome_adaptation", lang),
        }
        return messages.get(scenario, messages["university"])

    return welcome_text


# Инициализация обратной совместимости (синхронная загрузка из YAML)
import yaml
from pathlib import Path

_REGISTRY_PATH = Path(__file__).parent.parent / "prompts" / "registry.yaml"

def _load_prompts_sync():
    """Синхронная загрузка промптов из YAML для обратной совместимости"""
    global SYSTEM_PROMPTS, STYLE_RULES
    try:
        with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        
        prompts = data.get("prompts", {})
        SYSTEM_PROMPTS = {}
        for name in ("university", "job", "adaptation"):
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
import os
import asyncio
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile

from bot.translations import t
from bot.utils.pdf_export import generate_report
from bot.utils.lang import get_lang
from bot.database.db import get_user_stats, get_case_answers, get_or_create_user

router = Router()
logger = logging.getLogger(__name__)


async def generate_report_outcomes(user_id: int, scenarios: dict) -> list[tuple[str, str | None]]:
    """Сгенерировать PDF-отчёты по завершённым сценариям; None = ошибка"""
    outcomes = []
    for scenario, data in scenarios.items():
        if data["sessions"] <= 0:
            continue
        case_answers = await get_case_answers(user_id, scenario)
        results = [
            {"score": a["score"], "feedback": a.get("feedback", "")}
            for a in case_answers
        ] if case_answers else [
            {"score": data["avg_score"], "feedback": "Средний балл по сценарию"}
        ]
        try:
            path = await asyncio.to_thread(
                generate_report, user_id, scenario, results, case_answers
            )
            outcomes.append((scenario, path))
        except Exception as e:
            logger.error(f"Ошибка генерации PDF: {e}")
            outcomes.append((scenario, None))
    return outcomes


@router.callback_query(F.data == "export_pdf")
async def cb_export_pdf(cb: CallbackQuery):
    """Экспорт результатов в PDF"""
    user_id = cb.from_user.id
    user_data = await get_or_create_user(user_id)
    lang = get_lang(user_data)

    await cb.message.answer(t("pdf_generating", lang))
    await cb.bot.send_chat_action(cb.message.chat.id, "upload_document")

    stats = await get_user_stats(user_id)

    if not stats.get("scenarios"):
        await cb.message.answer(t("pdf_no_results", lang))
        await cb.answer()
        return

    success_count = 0
    for scenario, path in await generate_report_outcomes(user_id, stats["scenarios"]):
        if path is None:
            await cb.message.answer(t("pdf_error", lang, scenario=scenario))
            continue
        await cb.message.answer_document(
            FSInputFile(path),
            caption=t("pdf_caption", lang, scenario=scenario),
        )
        success_count += 1
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    if success_count > 0:
        await cb.message.answer(t("pdf_ready", lang))
    await cb.answer()

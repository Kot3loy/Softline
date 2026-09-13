import os
import asyncio
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile

from bot.utils.pdf_export import generate_report
from bot.database.db import get_user_stats, get_case_answers

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "export_pdf")
async def cb_export_pdf(cb: CallbackQuery):
    """Экспорт результатов в PDF"""
    user_id = cb.from_user.id

    await cb.message.answer("📥 Генерирую отчёт...")
    await cb.bot.send_chat_action(cb.message.chat.id, "upload_document")

    stats = await get_user_stats(user_id)

    if not stats.get("scenarios"):
        await cb.message.answer(
            "📊 У тебя пока нет результатов.\n"
            "Пройди хотя бы одно задание, чтобы я мог сгенерировать отчёт."
        )
        await cb.answer()
        return

    success_count = 0
    for scenario, data in stats["scenarios"].items():
        if data["sessions"] > 0:
            case_answers = await get_case_answers(user_id, scenario)
            results = [
                {"score": a["score"], "feedback": a.get("feedback", "")}
                for a in case_answers
            ] if case_answers else [
                {"score": data["avg_score"], "feedback": "Средний балл по сценарию"}
            ]

            try:
                report_path = await asyncio.to_thread(
                    generate_report, user_id, scenario, results, case_answers
                )
                await cb.message.answer_document(
                    FSInputFile(report_path),
                    caption=f"📄 Отчёт: {scenario}",
                )
                success_count += 1
                # Удаляем PDF после отправки
                try:
                    if os.path.exists(report_path):
                        os.remove(report_path)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Ошибка генерации PDF: {e}")
                await cb.message.answer(f"❌ Не удалось сгенерировать отчёт для {scenario}")

    if success_count > 0:
        await cb.message.answer(
            "✅ Отчёт готов!\n\n"
            "⚠️ Рекомендации носят информационный характер и не заменяют "
            "официальные требования вузов и работодателей.",
        )
    await cb.answer()

from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile

from bot.utils.pdf_export import generate_report
from bot.database.db import get_user_stats, get_case_answers

router = Router()


@router.callback_query(F.data == "export_pdf")
async def cb_export_pdf(cb: CallbackQuery):
    """Экспорт результатов в PDF"""
    user_id = cb.from_user.id

    await cb.message.answer("📥 Генерирую отчёт...")
    await cb.bot.send_chat_action(cb.message.chat.id, "upload_document")

    # Получаем статистику
    stats = await get_user_stats(user_id)

    if not stats.get("scenarios"):
        await cb.message.answer(
            "📊 У тебя пока нет результатов.\n"
            "Пройди хотя бы одно задание, чтобы я мог сгенерировать отчёт."
        )
        await cb.answer()
        return

    # Генерируем отчёт для каждого сценария
    for scenario, data in stats["scenarios"].items():
        if data["sessions"] > 0:
            # Получаем реальные ответы из БД
            case_answers = await get_case_answers(user_id, scenario)
            results = [
                {"score": a["score"], "feedback": a.get("feedback", "")}
                for a in case_answers
            ] if case_answers else [
                {"score": data["avg_score"], "feedback": "Средний балл по сценарию"}
            ]

            report_path = generate_report(user_id, scenario, results, case_answers)

            # Отправляем файл
            await cb.message.answer_document(
                FSInputFile(report_path),
                caption=f"📄 Отчёт: {scenario}",
            )

    await cb.message.answer(
        "✅ Отчёт готов!\n\n"
        "⚠️ Рекомендации носят информационный характер и не заменяют "
        "официальные требования вузов и работодателей.",
    )
    await cb.answer()

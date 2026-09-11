import logging
from fpdf import FPDF
from pathlib import Path
from bot.config import config

logger = logging.getLogger(__name__)


class PDFReport(FPDF):
    """Класс для генерации PDF-отчётов"""

    def header(self):
        self.set_font("DejaVu", "B", 16)
        self.cell(0, 10, "AI-наставник: Отчёт", align="C")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVu", "I", 8)
        self.cell(0, 10, f"Стр. {self.page_no()}", align="C")

    def chapter_title(self, title: str):
        self.set_font("DejaVu", "B", 14)
        self.cell(0, 10, title)
        self.ln(10)

    def chapter_body(self, body: str):
        self.set_font("DejaVu", "", 11)
        self.multi_cell(0, 7, body)
        self.ln(3)

    def add_score(self, label: str, score: int, max_score: int = 10):
        self.set_font("DejaVu", "B", 11)
        self.cell(0, 7, f"{label}: {score}/{max_score}")
        self.ln(7)

        # Прогресс-бар
        bar_width = 100
        filled = (score / max_score) * bar_width
        self.set_fill_color(200, 200, 200)
        self.rect(self.get_x(), self.get_y(), bar_width, 5, "F")
        self.set_fill_color(52, 152, 219)
        self.rect(self.get_x(), self.get_y(), filled, 5, "F")
        self.ln(8)


def generate_report(user_id: int, scenario: str, results: list, case_answers: list = None) -> str:
    """Сгенерировать PDF-отчёт"""
    from bot.core.adaptive import get_recommendations

    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/dejavu-sans.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/DejaVuSans.ttf",
    ]
    font_path = None
    for p in font_paths:
        if Path(p).exists():
            font_path = Path(p)
            break

    if not font_path:
        logger.warning("Шрифт не найден, пробуем встроенный шрифт FPDF")
        # Если шрифт не найден — используем встроенный шрифт FPDF (latin-1)
        # Кириллица может отображаться некорректно, но PDF не крашнется
        pdf = PDFReport()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Report", align="C")
        pdf.ln(10)
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 7, "Font not found. Install DejaVu Sans for proper Russian text rendering.")
        import time
        output_dir = config.DATA_DIR / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = int(time.time())
        output_path = output_dir / f"report_{user_id}_{scenario}_{timestamp}.pdf"
        pdf.output(str(output_path))
        return str(output_path)

    pdf = PDFReport()
    pdf.add_font("DejaVu", "", str(font_path), uni=True)
    pdf.add_font("DejaVu", "B", str(font_path), uni=True)
    pdf.add_font("DejaVu", "I", str(font_path), uni=True)
    pdf.add_page()

    # Заголовок
    scenario_names = {
        "university": "Выбор вуза",
        "job": "Поиск работы",
        "adaptation": "Адаптация в компании",
    }
    pdf.chapter_title(f"Сценарий: {scenario_names.get(scenario, scenario)}")

    # Детали по заданиям из БД
    if case_answers:
        total_score = sum(a.get("score", 0) for a in case_answers)
        avg_score = total_score / len(case_answers)

        pdf.add_score("Средний балл", round(avg_score))
        pdf.ln(5)

        pdf.chapter_title("Детали по заданиям:")
        for i, answer in enumerate(case_answers, 1):
            score = answer.get("score", 0)
            feedback = answer.get("feedback", "Нет обратной связи")
            case_id = answer.get("case_id", f"#{i}")

            pdf.set_font("DejaVu", "B", 11)
            pdf.cell(0, 7, f"Задание {i} ({case_id}): {score}/10")
            pdf.ln(7)
            pdf.set_font("DejaVu", "", 10)
            pdf.multi_cell(0, 6, feedback)
            pdf.ln(2)
    elif results:
        total_score = sum(r.get("score", 0) for r in results)
        avg_score = total_score / len(results)

        pdf.add_score("Средний балл", round(avg_score))
        pdf.ln(5)

        pdf.chapter_title("Детали:")
        for i, result in enumerate(results, 1):
            score = result.get("score", 0)
            feedback = result.get("feedback", "Нет обратной связи")
            pdf.set_font("DejaVu", "B", 11)
            pdf.cell(0, 7, f"Задание {i}: {score}/10")
            pdf.ln(7)
            pdf.set_font("DejaVu", "", 10)
            pdf.multi_cell(0, 6, feedback)
            pdf.ln(2)
    else:
        pdf.chapter_body("Пока нет результатов. Пройди хотя бы одно задание!")

    # Персонализированные рекомендации
    pdf.add_page()
    pdf.chapter_title("Рекомендации")

    # Получаем персонализированные рекомендации из системы адаптивного обучения
    recs = get_recommendations(user_id, scenario)
    if recs:
        recs_text = "\n".join(f"• {r}" for r in recs)
        pdf.chapter_body(recs_text)
    else:
        # Общие рекомендации если персонализированных нет
        pdf.chapter_body(
            "1. Повтори задания с низким баллом\n"
            "2. Обрати внимание на типичные ошибки\n"
            "3. Практикуйся регулярно\n"
            "4. Задавай вопросы в информационном режиме"
        )

    # Источники
    pdf.chapter_body(
        "\nИсточники:\n"
        "• Официальные сайты вузов и компаний\n"
        "• Отзывы студентов и сотрудников (habr.com, vc.ru)\n"
        "• Статьи по профориентации (ria.ru, lenta.ru)\n"
        "• Академическая литература по карьерному консультированию"
    )

    # Сохраняем с уникальным именем (timestamp)
    import time
    output_dir = config.DATA_DIR / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    output_path = output_dir / f"report_{user_id}_{scenario}_{timestamp}.pdf"

    pdf.output(str(output_path))
    logger.info(f"Отчёт сгенерирован: {output_path}")
    return str(output_path)

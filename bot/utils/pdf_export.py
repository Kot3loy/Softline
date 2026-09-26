import logging
import time
from pathlib import Path
from fpdf import FPDF
from bot.config import config
from bot.translations import t
from bot.core.adaptive import get_recommendations

logger = logging.getLogger(__name__)


class PDFReport(FPDF):

    _use_dejavu = False

    def __init__(self, lang="ru"):
        super().__init__()
        self.lang = lang

    def header(self):
        font = "DejaVu" if self._use_dejavu else "Helvetica"
        self.set_font(font, "B", 16)
        title = "AI-mentor: Report" if self.lang == "en" else "AI-наставник: Отчёт"
        self.cell(0, 10, title, align="C")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        font = "DejaVu" if self._use_dejavu else "Helvetica"
        self.set_font(font, "I", 8)
        page_text = f"Page {self.page_no()}" if self.lang == "en" else f"Стр. {self.page_no()}"
        self.cell(0, 10, page_text, align="C")

    def chapter_title(self, title):
        font = "DejaVu" if self._use_dejavu else "Helvetica"
        self.set_font(font, "B", 14)
        self.cell(0, 10, title)
        self.ln(10)

    def chapter_body(self, body):
        font = "DejaVu" if self._use_dejavu else "Helvetica"
        self.set_font(font, "", 11)
        self.multi_cell(0, 7, body)
        self.ln(3)

    def add_score(self, label, score, max_score=10):
        font = "DejaVu" if self._use_dejavu else "Helvetica"
        self.set_font(font, "B", 11)
        self.cell(0, 7, f"{label}: {score}/{max_score}")
        self.ln(7)

        bar_width = 100
        filled = (score / max_score) * bar_width
        self.set_fill_color(200, 200, 200)
        self.rect(self.get_x(), self.get_y(), bar_width, 5, "F")
        self.set_fill_color(52, 152, 219)
        self.rect(self.get_x(), self.get_y(), filled, 5, "F")
        self.ln(8)


def _find_font():
    # фпдф из коробки кириллицу не печатает — ищем шрифт дежаю на машине
    font_paths = [
        # DejaVu — отличная поддержка кириллицы
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/dejavu-sans.ttf",
        "/System/Library/Fonts/DejaVuSans.ttf",
        # Arial — поддерживает кириллицу на Windows
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for p in font_paths:
        if Path(p).exists():
            return Path(p)
    return None


def generate_report(user_id, scenario, results, case_answers=None, lang="ru"):
    # сам отчёт: сценарий, баллы по заданиям, рекомендации, источники, дисклеймер
    font_path = _find_font()
    use_dejavu = font_path is not None

    pdf = PDFReport(lang=lang)
    pdf._use_dejavu = use_dejavu
    if use_dejavu:
        pdf.add_font("DejaVu", "", str(font_path), uni=True)
        pdf.add_font("DejaVu", "B", str(font_path), uni=True)
        pdf.add_font("DejaVu", "I", str(font_path), uni=True)
    else:
        logger.warning("Шрифт DejaVu не найден, используем встроенный Helvetica")

    pdf.add_page()

    # Сценарий
    scenario_names = {
        "university": t("btn_university", lang).lstrip("🎓 "),
        "job": t("btn_job", lang).lstrip("💼 "),
        "adaptation": t("btn_adaptation", lang).lstrip("🤝 "),
    }
    chapter_label = "Scenario" if lang == "en" else "Сценарий"
    pdf.chapter_title(f"{chapter_label}: {scenario_names.get(scenario, scenario)}")

    # Детали по заданиям
    if case_answers:
        total_score = sum(a.get("score", 0) for a in case_answers)
        avg_score = total_score / max(len(case_answers), 1)

        avg_label = "Average score" if lang == "en" else "Средний балл"
        pdf.add_score(avg_label, round(avg_score))
        pdf.ln(5)

        # честно показываем сколько отвечено, а сколько было всего
        cases_total = max(
            (a.get("cases_total") or 0 for a in case_answers if a.get("cases_total")),
            default=len(case_answers),
        )
        answered_label = (
            f"Answered: {len(case_answers)} of {cases_total}"
            if lang == "en"
            else f"Отвечено заданий: {len(case_answers)} из {cases_total}"
        )
        pdf.chapter_body(answered_label)
        if cases_total > len(case_answers):
            skipped_label = (
                f"Skipped: {cases_total - len(case_answers)}"
                if lang == "en"
                else f"Пропущено заданий: {cases_total - len(case_answers)}"
            )
            pdf.chapter_body(skipped_label)
        pdf.ln(3)

        details_label = "Task details:" if lang == "en" else "Детали по заданиям:"
        pdf.chapter_title(details_label)
        for answer in case_answers:
            score = answer.get("score", 0)
            feedback = answer.get("feedback", "")
            case_id = answer.get("case_id", "")
            # реальный номер задания из case_id вида job_5
            number = case_id.rsplit("_", 1)[-1] if "_" in case_id else "?"

            task_label = "Task" if lang == "en" else "Задание"
            pdf.set_font("DejaVu" if pdf._use_dejavu else "Helvetica", "B", 11)
            pdf.cell(0, 7, f"{task_label} {number} ({case_id}): {score}/10")
            pdf.ln(7)
            pdf.set_font("DejaVu" if pdf._use_dejavu else "Helvetica", "", 10)
            pdf.multi_cell(0, 6, feedback)
            pdf.ln(2)
    else:
        # без ответов не выдумываем задания — просто говорим, что данных нет
        no_results = t("pdf_no_results", lang)
        pdf.chapter_body(no_results)

    # Рекомендации
    pdf.add_page()
    recs_label = "Recommendations" if lang == "en" else "Рекомендации"
    pdf.chapter_title(recs_label)

    recs = get_recommendations(user_id, scenario, lang)
    if recs:
        recs_text = "\n".join(f"• {r}" for r in recs)
        pdf.chapter_body(recs_text)
    else:
        if lang == "en":
            pdf.chapter_body(
                "1. Review tasks with low scores\n"
                "2. Pay attention to typical mistakes\n"
                "3. Practice regularly\n"
                "4. Ask questions in info mode"
            )
        else:
            pdf.chapter_body(
                "1. Повтори задания с низким баллом\n"
                "2. Обрати внимание на типичные ошибки\n"
                "3. Практикуйся регулярно\n"
                "4. Задавай вопросы в информационном режиме"
            )

    # Источники
    if lang == "en":
        pdf.chapter_body(
            "\nSources:\n"
            "- Official university and company websites\n"
            "- Student and employee reviews (habr.com, vc.ru)\n"
            "- Career guidance articles (ria.ru, lenta.ru)\n"
            "- Academic literature on career consulting"
        )
    else:
        pdf.chapter_body(
            "\nИсточники:\n"
            "• Официальные сайты вузов и компаний\n"
            "• Отзывы студентов и сотрудников (habr.com, vc.ru)\n"
            "• Статьи по профориентации (ria.ru, lenta.ru)\n"
            "• Академическая литература по карьерному консультированию"
        )

    # Дисклеймер
    disclaimer_label = "Disclaimer" if lang == "en" else "Дисклеймер"
    pdf.chapter_title(disclaimer_label)
    # вырезаю эмодзи из дисклеймера — шрифт дежаю его не знает
    disclaimer_text = t("disclaimer", lang).strip().lstrip("\u26a0\ufe0f").strip()
    pdf.chapter_body(disclaimer_text)

    output_dir = config.DATA_DIR / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    output_path = output_dir / f"report_{user_id}_{scenario}_{timestamp}.pdf"

    pdf.output(str(output_path))
    logger.info(f"Отчёт сгенерирован: {output_path}")
    return str(output_path)
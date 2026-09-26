"""Проверки правдивости PDF-отчёта: реальные номера заданий, честные счётчики,
без выдуманных строк."""

import os

from bot.utils.pdf_export import PDFReport, generate_report


def _capture(monkeypatch):
    titles, bodies, cells = [], [], []
    monkeypatch.setattr(PDFReport, "chapter_title", lambda self, x: titles.append(x))
    monkeypatch.setattr(PDFReport, "chapter_body", lambda self, b: bodies.append(b))
    monkeypatch.setattr(
        PDFReport,
        "add_score",
        lambda self, label, score, max_score=10: bodies.append(f"{label}: {score}"),
    )
    monkeypatch.setattr(
        PDFReport, "cell", lambda self, *a, **kw: cells.append(a[2] if len(a) > 2 else "")
    )
    return titles, bodies, cells


def _clean(path):
    if os.path.exists(path):
        os.remove(path)


def test_report_uses_real_task_numbers(monkeypatch):
    """Номер задания берётся из case_id, а не пересобирается с единицы"""
    titles, bodies, cells = _capture(monkeypatch)

    case_answers = [
        {"case_id": "job_2", "score": 8, "feedback": "хорошо", "user_answer": "ответ"},
        {"case_id": "job_5", "score": 4, "feedback": "слабо", "user_answer": "ответ"},
    ]
    path = generate_report(999999902, "job", [], case_answers)
    try:
        joined = " ".join(cells)
        assert "job_2" in joined
        assert "job_5" in joined
        # выдуманного первого задания быть не должно
        assert "Задание 1" not in joined
        assert "Task 1" not in joined
    finally:
        _clean(path)


def test_report_shows_answered_count(monkeypatch):
    """В отчёте видно, сколько заданий отвечено, а сколько всего было"""
    titles, bodies, cells = _capture(monkeypatch)

    case_answers = [
        {
            "case_id": "job_1",
            "score": 6,
            "feedback": "норм",
            "user_answer": "ответ",
            "cases_total": 5,
        },
    ]
    path = generate_report(999999903, "job", [], case_answers)
    try:
        joined = " ".join(bodies + cells)
        assert "1" in joined
        assert "5" in joined
    finally:
        _clean(path)


def test_report_without_answers_has_no_fake_task(monkeypatch):
    """Без ответов не рисуем выдуманную строку про средний балл"""
    titles, bodies, cells = _capture(monkeypatch)

    path = generate_report(
        999999904, "job", [{"score": 5, "feedback": "Средний балл по сценарию"}]
    )
    try:
        joined = " ".join(cells)
        assert "Средний балл по сценарию" not in joined
    finally:
        _clean(path)

"""Тесты генерации PDF-отчёта."""

import os

from bot.utils.pdf_export import generate_report, PDFReport


def test_pdf_report_includes_disclaimer(monkeypatch):
    """В PDF-отчёт попадает дисклеймер из реестра переводов"""
    bodies = []
    monkeypatch.setattr(
        PDFReport, "chapter_body", lambda self, body: bodies.append(body)
    )

    path = generate_report(999999901, "university", [{"score": 8, "feedback": "ok"}])
    try:
        assert any(
            "информационный характер" in b for b in bodies
        ), "дисклеймер не добавлен в отчёт"
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_pdf_report_includes_disclaimer_en(monkeypatch):
    """EN-версия отчёта тоже содержит дисклеймер"""
    bodies = []
    monkeypatch.setattr(
        PDFReport, "chapter_body", lambda self, body: bodies.append(body)
    )

    path = generate_report(
        999999901, "job", [{"score": 7, "feedback": "ok"}], lang="en"
    )
    try:
        assert any(
            "informational purposes" in b for b in bodies
        ), "disclaimer not added to report"
    finally:
        if os.path.exists(path):
            os.remove(path)

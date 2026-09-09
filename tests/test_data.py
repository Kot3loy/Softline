import pytest
from pathlib import Path
from bot.config import config


def test_university_files_exist():
    """Тест что файлы университетов существуют"""
    univ_dir = config.UNIVERSITIES_DIR
    files = list(univ_dir.glob("*.md"))
    assert len(files) > 0, "Нет файлов университетов"
    print(f"Найдено {len(files)} файлов университетов")


def test_company_files_exist():
    """Тест что файлы компаний существуют"""
    comp_dir = config.COMPANIES_DIR
    files = list(comp_dir.glob("*.md"))
    assert len(files) > 0, "Нет файлов компаний"
    print(f"Найдено {len(files)} файлов компаний")


def test_interview_files_exist():
    """Тест что файлы методичек существуют"""
    int_dir = config.INTERVIEWS_DIR
    files = list(int_dir.glob("*.md"))
    assert len(files) > 0, "Нет файлов методичек"
    print(f"Найдено {len(files)} файлов методичек")


def test_case_files_exist():
    """Тест что файлы кейсов существуют"""
    case_dir = config.CASES_DIR
    files = list(case_dir.glob("*.md"))
    assert len(files) >= 30, f"Найдено только {len(files)} файлов кейсов (нужно 30)"
    print(f"Найдено {len(files)} файлов кейсов")

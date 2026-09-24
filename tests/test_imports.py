"""Integration test — проверяет что все модули импортируются без ошибок."""

import importlib
import pytest


ALL_MODULES = [
    "bot.config",
    "bot.database.db",
    "bot.core.ai_engine",
    "bot.core.rag",
    "bot.core.adaptive",
    "bot.core.scenarios",
    "bot.core.common_mistakes",
    "bot.utils.keyboards",
    "bot.utils.voice",
    "bot.utils.pdf_export",
    "bot.handlers.start",
    "bot.handlers.info",
    "bot.handlers.examiner",
    "bot.handlers.voice",
    "bot.handlers.pdf_export",
    "bot.handlers.inline",
]


def test_all_modules_import():
    """Каждый модуль должен импортироваться без ошибок"""
    failed = []
    for module_name in ALL_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as e:
            failed.append(f"{module_name}: {e}")

    assert not failed, (
        "Сломанные импорты:\n" + "\n".join(f"  - {f}" for f in failed)
    )


def test_main_py_import_chain():
    """Повторяет цепочку импортов из bot/main.py"""
    from bot.handlers import start, info, examiner, voice, pdf_export, inline

    assert hasattr(start, "router")
    assert hasattr(info, "router")
    assert hasattr(examiner, "router")
    assert hasattr(voice, "router")
    assert hasattr(pdf_export, "router")
    assert hasattr(inline, "router")


def test_main_function_callable():
    """bot.main.main() должна быть вызываемой"""
    from bot.main import main
    assert callable(main)

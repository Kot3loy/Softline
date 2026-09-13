"""Integration test — проверяет что все модули импортируются без ошибок.

Этот тест повторяет цепочку импортов из bot/main.py:155:
    from bot.handlers import start, info, examiner, voice, pdf_export, admin

Если этот тест падает — бот не запустится.
"""

import importlib
import pytest


# Все модули которые импортируются при реальном запуске бота
# Порядок важен — как в bot/main.py
ALL_MODULES = [
    # Конфиг и БД
    "bot.config",
    "bot.database.db",
    # Ядро
    "bot.core.ai_engine",
    "bot.core.rag",
    "bot.core.adaptive",
    "bot.core.scenarios",
    "bot.core.common_mistakes",
    # Утилиты
    "bot.utils.keyboards",
    "bot.utils.voice",
    "bot.utils.pdf_export",
    # Хендлеры (именно в этом порядке как в main.py)
    "bot.handlers.start",
    "bot.handlers.info",
    "bot.handlers.examiner",
    "bot.handlers.voice",
    "bot.handlers.pdf_export",
    "bot.handlers.admin",
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
    """Повторяет точную цепочку импортов из bot/main.py:155"""
    from bot.handlers import start, info, examiner, voice, pdf_export, admin

    # Все роутеры должны иметь атрибут router
    assert hasattr(start, "router")
    assert hasattr(info, "router")
    assert hasattr(examiner, "router")
    assert hasattr(voice, "router")
    assert hasattr(pdf_export, "router")
    assert hasattr(admin, "router")


def test_main_function_callable():
    """bot.main.main() должна быть вызываемой"""
    from bot.main import main
    assert callable(main)

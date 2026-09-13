"""Конфигурация бота — загрузка переменных окружения из .env файла."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Грузим .env из корня проекта
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Основные настройки бота, загружаемые из переменных окружения."""

    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # Админы (ID через запятую)
    ADMIN_IDS: list[int] = []
    try:
        ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
    except ValueError:
        print("⚠️ ADMIN_IDS содержит нечисловые значения", file=sys.stderr)

    # GigaChat
    GIGACHAT_CREDENTIALS: str = os.getenv("GIGACHAT_CREDENTIALS", "")
    GIGACHAT_MODEL: str = os.getenv("GIGACHAT_MODEL", "GigaChat")
    GIGACHAT_VERIFY_SSL_CERTS: bool = os.getenv("GIGACHAT_VERIFY_SSL_CERTS", "false").lower() == "true"

    # ChromaDB
    CHROMA_DIR: Path = BASE_DIR / os.getenv("CHROMA_DIR", "chroma_db")
    try:
        CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
    except (ValueError, TypeError):
        CHUNK_SIZE: int = 1000
    try:
        CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))
    except (ValueError, TypeError):
        CHUNK_OVERLAP: int = 200

    # SQLite
    DATABASE_DIR: Path = BASE_DIR / os.getenv("DATABASE_DIR", "database")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "bot.db")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: Path = BASE_DIR / os.getenv("LOG_FILE", "bot.log")

    # Пути к данным
    DATA_DIR: Path = BASE_DIR / "data"
    UNIVERSITIES_DIR: Path = DATA_DIR / "universities"
    COMPANIES_DIR: Path = DATA_DIR / "companies"
    INTERVIEWS_DIR: Path = DATA_DIR / "interviews"
    CASES_DIR: Path = DATA_DIR / "cases"


config = Config()


def validate_config():
    """Проверить что критичные переменные заданы.
    Вызывать ТОЛЬКО при реальном запуске бота, не при импорте.
    """
    errors = []
    if not config.BOT_TOKEN:
        errors.append("BOT_TOKEN не задан")
    if not config.GIGACHAT_CREDENTIALS:
        errors.append("GIGACHAT_CREDENTIALS не задан")
    if errors:
        print("❌ Ошибка конфигурации:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print("\nСоздай файл .env из .env.example и заполни его.", file=sys.stderr)
        sys.exit(1)


def check_config() -> list[str]:
    """Проверить конфиг и вернуть список ошибок (не крашит)."""
    errors = []
    if not config.BOT_TOKEN:
        errors.append("BOT_TOKEN не задан")
    if not config.GIGACHAT_CREDENTIALS:
        errors.append("GIGACHAT_CREDENTIALS не задан")
    return errors

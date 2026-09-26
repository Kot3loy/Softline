# конфиг: всё что нужно боту берём из .env

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")

    GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS", "")
    GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat")
    GIGACHAT_VERIFY_SSL_CERTS = os.getenv("GIGACHAT_VERIFY_SSL_CERTS", "true").lower() == "true"

    DATABASE_DIR = BASE_DIR / os.getenv("DATABASE_DIR", "database")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "bot.db")

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = BASE_DIR / os.getenv("LOG_FILE", "bot.log")

    DATA_DIR = BASE_DIR / "data"
    UNIVERSITIES_DIR = DATA_DIR / "universities"
    COMPANIES_DIR = DATA_DIR / "companies"
    INTERVIEWS_DIR = DATA_DIR / "interviews"
    CASES_DIR = DATA_DIR / "cases"


config = Config()


def validate_config():
    # если чего-то не хватает в .env — сразу падаем с понятной ошибкой
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
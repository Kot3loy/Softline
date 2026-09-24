import pytest
from bot.config import config


def test_config_loads():
    """Тест что конфигурация загружается"""
    assert config.BOT_TOKEN is not None
    assert config.GIGACHAT_CREDENTIALS is not None


def test_config_paths():
    """Тест что пути настроены"""
    assert config.DATA_DIR.exists()
    assert config.DATABASE_DIR is not None


def test_data_directories():
    """Тест что папки с данными существуют"""
    assert config.UNIVERSITIES_DIR.exists()
    assert config.COMPANIES_DIR.exists()
    assert config.INTERVIEWS_DIR.exists()
    assert config.CASES_DIR.exists()

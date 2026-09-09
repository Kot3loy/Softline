import pytest
from bot.core.scenarios import SYSTEM_PROMPTS, STYLE_RULES


def test_all_scenarios_have_prompts():
    """Тест что все сценарии имеют системные промпты"""
    required = ["university", "job", "adaptation"]
    for scenario in required:
        assert scenario in SYSTEM_PROMPTS, f"Нет промпта для сценария: {scenario}"


def test_style_rules_present():
    """Тест что стиль общения определён"""
    assert "русском" in STYLE_RULES
    assert len(STYLE_RULES) > 100


def test_prompts_contain_disclaimer():
    """Тест что все промпты содержат ограничение области"""
    for scenario, prompt in SYSTEM_PROMPTS.items():
        assert "ГРАНИЦЫ" in prompt or "помогаю только" in prompt, (
            f"Ограничение области отсутствует в сценарии: {scenario}"
        )


def test_prompts_contain_scope_restriction():
    """Тест что промпты ограничивают область ответов"""
    for scenario, prompt in SYSTEM_PROMPTS.items():
        assert "Не отвечай" in prompt or "не отвечай" in prompt, (
            f"Ограничение области отсутствует в сценарии: {scenario}"
        )

"""Тесты prompt registry — загрузка, fallback, register/rollback."""

from bot.core.prompt_registry import PromptRegistry, prompt_registry, load_prompts_from_registry


def test_registry_loads_with_prompts_and_versions():
    """Реестр загружается: dict с prompts + versions, у промпта current + versions"""
    assert isinstance(prompt_registry.registry, dict)
    assert "prompts" in prompt_registry.registry
    assert "versions" in prompt_registry.registry

    uni = prompt_registry.registry["prompts"]["university"]
    assert "current" in uni
    assert "versions" in uni
    assert uni["current"] == "v1"


def test_get_content_returns_current_version_body():
    content = prompt_registry.get_content("university")
    assert isinstance(content, str)
    assert len(content) > 100
    assert "ГРАНИЦЫ" in content


def test_get_content_all_registered_keys():
    for name in prompt_registry.registry["prompts"]:
        content = prompt_registry.get_content(name)
        assert isinstance(content, str) and content, f"empty content for {name}"


def test_get_content_missing_key_returns_none():
    assert prompt_registry.get_content("no_such_prompt") is None


def test_get_current():
    assert prompt_registry.get_current("university") == "v1"
    assert prompt_registry.get_current("missing") is None


def test_list_versions():
    versions = prompt_registry.list_versions("university")
    assert len(versions) >= 1
    assert versions[0]["version"] == "v1"
    assert prompt_registry.list_versions("missing") == []


def test_missing_file_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "bot.core.prompt_registry.REGISTRY_PATH", tmp_path / "does_not_exist.yaml"
    )
    reg = PromptRegistry()
    assert reg.registry == {"prompts": {}, "versions": []}
    assert reg.get_content("university") is None


def test_invalid_file_fallback_no_crash(monkeypatch, tmp_path):
    bad = tmp_path / "broken.yaml"
    bad.write_text("prompts: [unclosed\n  bad: {{", encoding="utf-8")
    monkeypatch.setattr("bot.core.prompt_registry.REGISTRY_PATH", bad)
    reg = PromptRegistry()
    assert reg.registry == {"prompts": {}, "versions": []}


def test_register_and_rollback_happy_path(monkeypatch, tmp_path):
    target = tmp_path / "registry.yaml"
    monkeypatch.setattr("bot.core.prompt_registry.REGISTRY_PATH", target)
    reg = PromptRegistry()

    v1 = reg.register("demo", "content v1", author="tester")
    v2 = reg.register("demo", "content v2", author="tester")
    assert v1 == "v1"
    assert v2 == "v2"
    assert reg.get_content("demo") == "content v2"
    assert reg.get_current("demo") == "v2"

    assert reg.rollback("demo", "v1") is True
    assert reg.get_content("demo") == "content v1"
    assert reg.rollback("demo", "v99") is False

    assert target.exists()
    saved = target.read_text(encoding="utf-8")
    assert "content v1" in saved


def test_load_prompts_from_registry_active():
    active = load_prompts_from_registry()
    assert isinstance(active, dict)
    assert "university" in active
    assert isinstance(active["university"], str)

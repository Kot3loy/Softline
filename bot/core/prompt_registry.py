# реестр промптов — храню версии промптов в registry.yaml
# чтобы потом можно было посмотреть старые версии и откатить

import logging
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List
from bot.config import config

logger = logging.getLogger(__name__)

REGISTRY_PATH = Path(__file__).parent.parent / "prompts" / "registry.yaml"


class PromptRegistry:
    def __init__(self):
        self.registry = self._load()

    def _load(self) -> dict:
        # читаю реестр из yaml
        if REGISTRY_PATH.exists():
            try:
                with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {"prompts": {}, "versions": []}
            except (yaml.YAMLError, OSError) as e:
                logger.warning(f"Не удалось загрузить реестр {REGISTRY_PATH}: {e}")
        return {"prompts": {}, "versions": []}

    def _save(self):
        # сохраняю реестр обратно в yaml
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            yaml.dump(self.registry, f, allow_unicode=True, sort_keys=False)

    def register(self, name: str, content: str, author: str = "system", description: str = "") -> str:
        # добавляю новую версию промпта
        now = datetime.now().isoformat()
        version = f"v{len(self.registry.get('versions', [])) + 1}"

        prompt_data = {
            "name": name,
            "version": version,
            "content": content,
            "author": author,
            "description": description,
            "created_at": now,
            "active": True,
        }

        if "prompts" not in self.registry:
            self.registry["prompts"] = {}
        if name not in self.registry["prompts"]:
            self.registry["prompts"][name] = {"versions": [], "current": version}

        self.registry["prompts"][name]["versions"].append(prompt_data)
        self.registry["prompts"][name]["current"] = version

        if "versions" not in self.registry:
            self.registry["versions"] = []
        self.registry["versions"].append({
            "name": name,
            "version": version,
            "author": author,
            "created_at": now,
            "description": description,
        })

        self._save()
        return version

    def get_current(self, name: str) -> Optional[str]:
        # какая сейчас версия у промпта
        return self.registry.get("prompts", {}).get(name, {}).get("current")

    def get_content(self, name: str, version: str | None = None) -> Optional[str]:
        # достать текст промпта (текущий или конкретную версию)
        if name not in self.registry.get("prompts", {}):
            return None

        prompt_info = self.registry["prompts"][name]
        target_version = version or prompt_info.get("current")

        if target_version is None:
            versions = prompt_info.get("versions", [])
            if versions:
                return versions[-1]["content"]
            return None

        for v in prompt_info.get("versions", []):
            if v["version"] == target_version:
                return v["content"]

        versions = prompt_info.get("versions", [])
        if versions and version is None:
            return versions[-1]["content"]
        return None

    def list_versions(self, name: str) -> List[dict]:
        # все версии промпта
        return self.registry.get("prompts", {}).get(name, {}).get("versions", [])

    def rollback(self, name: str, version: str) -> bool:
        # откатить к старой версии промпта
        if name in self.registry.get("prompts", {}) and version in [v["version"] for v in self.registry["prompts"][name].get("versions", [])]:
            self.registry["prompts"][name]["current"] = version
            self._save()
            return True
        return False

    def get_active_prompts(self) -> dict:
        # все промпты которые сейчас в статусе current
        result = {}
        for name, info in self.registry.get("prompts", {}).items():
            current = info.get("current")
            content = self.get_content(name, current)
            if content:
                result[name] = content
        return result


# Глобальный экземпляр
prompt_registry = PromptRegistry()


def load_prompts_from_registry() -> dict:
    # просто взять активные промпты из реестра
    return prompt_registry.get_active_prompts()
# AGENTS.md — Softline_bot1

Python Telegram-бот (aiogram, RAG, prompt registry, pytest). Следуй правилам ниже всегда.

## Обязательные скиллы (всегда использовать)

| Ситуация | Скилл |
|----------|-------|
| Любая фича / багфикс | `superpowers:test-driven-development` (red-green-refactor) перед имплементацией |
| Баг / неожиданное поведение | `superpowers:systematic-debugging` до предложений фиксов |
| Креатив / новая функциональность | `superpowers:brainstorming` до кода |
| Многошаговая задача | `superpowers:writing-plans` → `superpowers:executing-plans` |
| Работа с git (опасные команды) | `git-guardrails-claude-code` — не force-push, не reset --hard без проверки |
| Async / asyncio / aiogram | `async-python-patterns` |
| Написание и рефакторинг тестов | `python-testing-patterns` (дополняет superpowers TDD) |
| Внешние SaaS/API (Gmail, Slack, Notion, GitHub и т.д.) | `composio` |
| Свежие веб-данные, скрейп, crawl | `firecrawl` |
| Вопросы по структуре кодовой базы | `understand` / `understand-explain` |
| README, доки, release notes | `stop-slop` — финальная вычитка от AI-стиля |
| Конец длинной сессии / смена контекста | `handoff` |
| Новый SKILL.md | `skill-creator` |
| Ревью диффа | `code-review` или `superpowers:requesting-code-review` |

Правило 1%: если есть ≥1% шанс, что скилл применим — вызывай его.

## Команды проекта

```bash
# Тесты
.venv\Scripts\python.exe -m pytest tests/ -q

# Локальный запуск
.venv\Scripts\python.exe main.py
```

Windows + PowerShell: не использовать heredoc (`<<`). Скрипты писать в файл, затем запускать.

## Структура

- `bot/prompts/registry.yaml` — версионируемые промпты (поля `current` + `versions`)
- `bot/core/prompt_registry.py` — загрузчик реестра
- `bot/core/scenarios.py` — сценарии (university, job, adaptation)
- `data/` — вузы, компании, кейсы, интервью (markdown)
- `tests/` — pytest

## Конвенции

- Ответы пользователю в коде/доках/коммитах — обычный English/Russian по контексту проекта.
- Промпты в registry.yaml: единый отступ тела block scalar, всегда `current: v1` при новой версии.
- Не хардкодить секреты; `.env` не коммитить.
- После правок — прогон `pytest` перед «готово».

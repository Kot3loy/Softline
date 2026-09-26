# Руководство по развертыванию AI-наставника (AI-тренажёр для абитуриента и стажёра)

Полное руководство для разработчика, который хочет воссоздать проект с нуля.

---

## 📁 Структура файлов конфигурации

| Файл | Назначение | Обязательный? |
|------|------------|---------------|
| `requirements.txt` | Продакшн-зависимости (aiogram, GigaChat, edge-tts, PDF, БД и т.д.) | **Да** |
| `requirements-dev.txt` | Dev-зависимости для тестов (pytest, pytest-asyncio) | Только для разработки/тестов |
| `.env.example` | Шаблон переменных окружения — скопируйте в `.env` и заполните | **Да** |
| `.env` | **Ваши реальные секреты** (НЕ коммитить в git!) | **Да** |
| `render.yaml` | Конфиг деплоя на Render (web-сервис, free-тайр) | Для деплоя |
| `pyproject.toml` | Конфиг линтеров (ruff, mypy) и pytest | Для разработки |

---

## 🚀 Быстрый старт (Windows / Linux / macOS)

### 1. Клонирование и окружение

```bash
# Клонирование
git clone https://github.com/your-org/Softline_bot1.git
cd Softline_bot1

# Виртуальное окружение
python -m venv .venv

# Активация (Windows PowerShell)
.venv\Scripts\Activate.ps1
# Или Linux/macOS:
# source .venv/bin/activate
```

### 2. Установка зависимостей

```bash
# Продакшн-зависимости (ОБЯЗАТЕЛЬНО)
pip install -r requirements.txt

# Dev-зависимости (для тестов и линтеров — опционально)
pip install -r requirements-dev.txt
```

> **Важно:** `requirements-dev.txt` содержит только `pytest` и `pytest-asyncio`. Без него бот будет работать, но тесты не запустятся.

### 3. Установка ffmpeg (для голосового режима)

Без ffmpeg голосовой режим работать не будет (конвертация ogg→wav). Текстовый режим работает без ffmpeg.

| OS | Команда |
|----|---------|
| Windows | `winget install Gyan.FFmpeg` |
| Linux (Debian/Ubuntu) | `sudo apt update && sudo apt install ffmpeg` |
| macOS (Homebrew) | `brew install ffmpeg` |

> На Render ffmpeg скачивается автоматически при билде (см. `render.yaml`).

### 4. Переменные окружения (`.env`)

```bash
# Скопируйте шаблон
cp .env.example .env
```

Откройте `.env` в редакторе и заполните **все** поля:

| Переменная | Описание | Пример |
|------------|----------|--------|
| `BOT_TOKEN` | Токен бота от [@BotFather](https://t.me/BotFather) | `123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11` |
| `ADMIN_IDS` | Telegram User ID админов (через запятую) | `123456789,987654321` |
| `GIGACHAT_CREDENTIALS` | Авторизационный токен GigaChat (base64 от `client_id:client_secret`) | `base64_encoded_string` |
| `GIGACHAT_MODEL` | Модель GigaChat | `GigaChat-2` |
| `GIGACHAT_VERIFY_SSL_CERTS` | Проверка SSL сертификатов GigaChat | `true` (только `false` для локального теста с самоподписанными сертификатами) |
| `DATABASE_DIR` | Папка для SQLite БД | `./database` |
| `DATABASE_NAME` | Имя файла БД | `bot.db` |
| `LOG_LEVEL` | Уровень логирования | `INFO` |
| `LOG_FILE` | Файл логов | `bot.log` |

> **Как получить `GIGACHAT_CREDENTIALS`:**
> 1. Зарегистрируйтесь на [developers.sber.ru](https://developers.sber.ru)
> 2. Создайте приложение → получите `client_id` и `client_secret`
> 2. `echo -n "client_id:client_secret" | base64` → вставьте в `.env`

### 5. Запуск

```bash
# Локально
python main.py

# Или через модуль
python -m bot.main
```

Бот начнёт поллинг. Откройте Telegram → найдите бота → `/start`.

---

## 🧪 Запуск тестов

```bash
# Все тесты (236 шт.)
.venv\Scripts\python.exe -m pytest tests/ -q

# Конкретный файл
.venv\Scripts\python.exe -m pytest tests/test_voice.py -q

# С покрытием (если установлен pytest-cov)
.venv\Scripts\python.exe -m pytest tests/ --cov=bot --cov-report=term-missing
```

**Ожидаемый результат:** `236 passed` (на момент v1.0).

---

## 🔍 Линтеры и типы

```bash
# Ruff (быстрый линтер)
ruff check .

# MyPy (статическая типизация)
mypy bot/

# Форматирование (если нужно)
ruff format .
```

Конфигурация в `pyproject.toml`:
- `line-length = 100`
- `target-version = "py312"`
- Игноры: `E402` (импорты не в начале), `E501` (длинные строки), `I001` (сортировка импортов)
- Per-file ignores для тестов и отдельных файлов

---

## 📦 Деплой на Render (бесплатно)

### 1. Подготовка репозитория
```bash
git add .
git commit -m "Release"
git push origin main
```

### 2. На Render Dashboard
1. **New → Blueprint** → укажите GitHub-репозиторий
2. Render прочитает `render.yaml`:
   - Тип: `worker` (не web! бот делает поллинг)
   - План: `free`
   - Диск: 1 GB на `/opt/render/project/src/database` (SQLite)
   - `buildCommand`: качает ffmpeg статичным бинарником + `pip install -r requirements.txt`
   - `startCommand`: `python main.py`

### 3. Секреты (Environment Variables → Dashboard)
Добавьте как **Secret** (`sync: false`):
- `BOT_TOKEN`
- `GIGACHAT_CREDENTIALS`
- `ADMIN_IDS`
- (Опционально) `GIGACHAT_VERIFY_SSL_CERTS=true`

> `LOG_LEVEL`, `DATABASE_DIR`, `DATABASE_NAME` — можно оставить из `render.yaml` (не секреты).

### 4. Деплой
Нажмите **Deploy** → Render соберёт образ, скачает ffmpeg, установит зависимости, запустит бота.

---

## 🗂 Структура данных (data/)

```
data/
├── universities/   # 20 вузов (проходные, программы, цены)
├── companies/      # 14 компаний (стек, зарплаты, отзывы)
├── interviews/     # 3 кейса собеседований
└── cases/          # 30 кейсов-тренажёров (university/job/adaptation)
```

Каждый `.md` файл имеет **frontmatter**:
```yaml
---
scenario: universities
source_url: https://postupi.online/vuzi/msu/
tags: []
---
# Контент...
```

`source_url` используется ботом для цитирования источников в ответах ИИ.

---

## ⚙️ Полезные команды разработчика

```bash
# Перезапуск после изменений кода (бот не hot-reload)
# Просто перезапустите python main.py

# Очистка БД (сбросить прогресс пользователей)
rm database/bot.db

# Пересборка индекса RAG (после изменения data/)
# В коде: await rebuild_index() или перезапуск бота

# Просмотр логов
tail -f bot.log

# Проверка импортов
python -c "import bot; print('OK')"
```

---

## 🐛 Частые проблемы

| Проблема | Решение |
|----------|---------|
| `ModuleNotFoundError: bot` | Запускайте из корня проекта (`cd Softline_bot1`) |
| `ImportError: pydub` | `pip install pydub` + установлен ли ffmpeg? |
| `GigaChat API timeout` | Проверьте `GIGACHAT_CREDENTIALS`, интернет, `GIGACHAT_VERIFY_SSL_CERTS=true` |
| `ffmpeg not found` | Установите ffmpeg и перезапустите терминал |
| Бот не отвечает | Проверьте `BOT_TOKEN`, логи `bot.log`, запущен ли процесс |
| Тесты падают | `pip install -r requirements-dev.txt`, затем `pytest tests/ -q` |

---

## 📄 Лицензия

MIT — см. [LICENSE](LICENSE).

Проект создан для конкурса **SK Kids Challenge** от **Софтлайн Решения**.

---

## 📞 Контакты

- Автор: [ваш GitHub/Telegram]
- Компания: Софтлайн Решения
- Конкурс: SK Kids Challenge
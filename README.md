# AI-наставник — Telegram-бот для подготовки к поступлению и карьере

Telegram-бот — AI-тренажёр для абитуриентов и молодых специалистов (15–20 лет). Помогает с выбором вуза, поиском работы и адаптацией в компании.

Кейс **Софтлайн Решения** для конкурса **SK Kids Challenge**.

## Возможности

- **3 сценария:** выбор вуза, поиск работы, адаптация в компании
- **Информационный режим:** диалог с AI-наставником по выбранному сценарию
- **Режим экзаменатора:** практика на реальных заданиях с оценкой и обратной связью
- **Два типа заданий:** свободный ответ + тест с выбором варианта
- **Голосовой режим:** распознавание речи (STT) и синтез речи (TTS) с нейронными голосами Microsoft
- **Адаптивное обучение:** бот запоминает ошибки и акцентирует на слабых зонах
- **Экспорт в PDF:** персональный отчёт с результатами и рекомендациями
- **База знаний:** 67 файлов с данными о 20 вузах, 14 компаниях, 30 кейсах

## Архитектура

```
bot/
├── core/           # AI-движок, сценарии, RAG, адаптивное обучение
│   ├── ai_engine.py        # Генерация заданий, оценка ответов (GigaChat API)
│   ├── scenarios.py        # Системные промпты, информационный режим
│   ├── rag.py              # Поиск по базе знаний (keyword-based RAG)
│   ├── adaptive.py         # Отслеживание ошибок, персонализация
│   ├── prompt_registry.py  # Реестр версионируемых промптов
│   └── common_mistakes.py  # Каталог типичных ошибок для адаптивного обучения
├── handlers/       # Хендлеры Telegram-бота
│   ├── start.py        # Приветствие, главное меню, /help, /export
│   ├── info.py         # Информационный режим (диалог с AI)
│   ├── examiner.py     # Режим экзаменатора (задания + оценка)
│   ├── voice.py        # Голосовые сообщения (STT/TTS)
│   ├── pdf_export.py   # Генерация PDF-отчёта
│   └── inline.py       # Inline-кнопки и колбэки
├── utils/          # Утилиты
│   ├── keyboards.py    # Генерация клавиатур
│   ├── voice.py        # Синтез/распознавание речи (edge-tts, SpeechRecognition)
│   ├── pdf_export.py   # Генерация PDF (fpdf2)
│   └── translator.py   # Перевод ответов (GigaChat)
├── database/       # База данных
│   └── db.py           # SQLite через aiosqlite
├── prompts/
│   └── registry.yaml   # Версионируемые промпты (current + versions)
├── config.py       # Конфигурация из .env
├── translations.py # Локализация (ru/en)
├── main.py         # Точка входа бота (aiogram Dispatcher)
└── __init__.py
tests/            # Pytest-тесты
main.py           # Запуск бота (entrypoint)
```

## Стек технологий

| Компонент | Технология |
|-----------|------------|
| Фреймворк бота | aiogram 3.x |
| AI / LLM | GigaChat (Sber) |
| База знаний | Keyword-based RAG (TF-IDF + стемминг) |
| База данных | SQLite (aiosqlite) |
| Голос (TTS) | edge-tts (Microsoft Neural voices) |
| Голос (STT) | SpeechRecognition + Google |
| PDF-отчёт | fpdf2 |
| Адаптивное обучение | JSON-файл + анализ ошибок |

## Установка

### Локально

1. Клонируйте репозиторий:
```bash
git clone <url>
cd Softline_bot1
```

2. Создайте виртуальное окружение:
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Установите ffmpeg (опционально — без него голосовой режим деградирует, текстовый работает):
```bash
# Windows
winget install Gyan.FFmpeg

# Linux
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

5. Создайте файл `.env` из шаблона:
```bash
cp .env.example .env
```

6. Заполните `.env` вашими данными (все ключи из `.env.example`):
```
BOT_TOKEN=ваш_токен_бота
ADMIN_IDS=id_админа
GIGACHAT_CREDENTIALS=ваш_API_ключ_GigaChat
GIGACHAT_MODEL=GigaChat-2
GIGACHAT_VERIFY_SSL_CERTS=true
DATABASE_DIR=./database
DATABASE_NAME=bot.db
LOG_LEVEL=INFO
LOG_FILE=bot.log
```

7. Запустите бота:
```bash
python main.py
```

### Деплой на Render

Проект настроен для деплоя на Render через `render.yaml` (worker, free plan, диск 1 GB на `/database`).

1. Загрузите код на GitHub
2. В Render: New → Blueprint → подключите репозиторий
3. Добавьте секреты в Dashboard (sync: false):
   - `BOT_TOKEN`
   - `GIGACHAT_CREDENTIALS`
   - `ADMIN_IDS`
4. Render автоматически соберёт и запустит worker по `render.yaml`

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и главное меню |
| `/help` | Справка по функциям бота |
| `/export` | Генерация PDF-отчёта с результатами |

`/disclaimer` доступен в чате (обрабатывается вместе с `/help`), в Telegram-меню не зарегистрирован.

## Тесты

```bash
.venv\Scripts\python.exe -m pytest tests/ -q
```

## Лицензия

MIT — см. LICENSE.

Проект создан для участия в конкурсе **SK Kids Challenge** от компании **Софтлайн Решения**.
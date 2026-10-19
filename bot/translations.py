# все тексты бота в одном месте (русская и английская версии)

STRINGS = {
    # === START MENU ===
    "welcome_msg": {
        "ru": "👋 Привет! Я — твой <b>AI-наставник</b> от Softline.\n\n"
              "Помогу с выбором вуза, поиском работы и адаптацией в компании.\n\n"
              "Чем помочь?",
        "en": "👋 Hi! I'm your <b>AI mentor</b> from Softline.\n\n"
              "I'll help with university, job search, and adapting to a new company.\n\n"
              "What do you need?",
    },
    "btn_university": {"ru": "🎓 Выбор вуза", "en": "🎓 University"},
    "btn_job": {"ru": "💼 Поиск работы", "en": "💼 Job search"},
    "btn_adaptation": {"ru": "🤝 Адаптация в компании", "en": "🤝 Adaptation"},
    "btn_progress": {"ru": "📊 Прогресс", "en": "📊 Progress"},
    "btn_settings": {"ru": "⚙️ Настройки", "en": "⚙️ Settings"},

    # === ABOUT ===
    "about_header": {"ru": "ℹ️ <b>О боте</b>", "en": "ℹ️ <b>About bot</b>"},
    "about_desc": {
        "ru": "🤖 <b>AI-наставник</b> — бот для школьников и молодых специалистов.",
        "en": "🤖 <b>AI mentor</b> — bot for students and young professionals.",
    },
    "about_features": {"ru": "📌 <b>Что умею:</b>", "en": "📌 <b>Features:</b>"},
    "about_f1": {"ru": "• Помогаю с выбором вуза", "en": "• Help choose a university"},
    "about_f2": {"ru": "• Готовлю к собеседованиям", "en": "• Prepare for interviews"},
    "about_f3": {"ru": "• Помогаю адаптироваться на новой работе", "en": "• Help adapt to a new job"},
    "about_f4": {"ru": "• Проверяю знания в режиме экзаменатора", "en": "• Test knowledge in examiner mode"},
    "about_f5": {"ru": "• Говорю голосом (включи в настройках)", "en": "• Speak voice (enable in settings)"},
    "about_f6": {"ru": "• Составляю PDF-отчёты (/export)", "en": "• Generate PDF reports (/export)"},
    "about_howto": {"ru": "💡 <b>Как пользоваться:</b>", "en": "💡 <b>How to use:</b>"},
    "about_h1": {"ru": "• Выбери сценарий в меню", "en": "• Choose a scenario in menu"},
    "about_h2": {"ru": "• Задавай вопросы — отвечу", "en": "• Ask questions — I'll answer"},
    "about_h3": {"ru": "• В экзаменаторе отвечай на задания — дам обратную связь", "en": "• In examiner answer tasks — I'll give feedback"},
    "about_h4": {"ru": "• Отправляй голосовые сообщения — отвечу голосом", "en": "• Send voice messages — I'll reply with voice"},
    "about_settings": {"ru": "⚙️ <b>Настройки:</b> переключай язык и голос", "en": "⚙️ <b>Settings:</b> switch language and voice"},
    "about_progress": {"ru": "📊 <b>Прогресс:</b> смотри статистику", "en": "📊 <b>Progress:</b> view statistics"},
    "about_export": {"ru": "📥 <b>/export:</b> скачай PDF-отчёт", "en": "📥 <b>/export:</b> download PDF report"},
    "about_credits": {"ru": "👨‍💻 <b>Создан для:</b> SK Kids Challenge от Softline", "en": "👨‍💻 <b>Built for:</b> SK Kids Challenge by Softline"},
    "about_tech": {"ru": "🔧 <b>Технологии:</b> Python, aiogram, GigaChat, edge-tts", "en": "🔧 <b>Tech:</b> Python, aiogram, GigaChat, edge-tts"},
    "about_disclaimer": {
        "ru": "⚠️ <b>Дисклеймер:</b> рекомендации носят информационный характер и не заменяют "
              "официальные требования вузов и работодателей. Всегда проверяйте актуальную информацию на официальных сайтах.\n"
              "Не сообщайте боту личные данные (телефон, адрес, ФИО).",
        "en": "⚠️ <b>Disclaimer:</b> recommendations are for informational purposes only and do not replace "
              "official requirements of universities and employers. Always check current information on official websites.\n"
              "Do not share personal data (phone, address, full name) with the bot.",
    },

    # === SETTINGS ===
    "settings_header": {"ru": "⚙️ <b>Настройки</b>", "en": "⚙️ <b>Settings</b>"},
    "settings_voice_hint": {
        "ru": "🎙 Голосовые принимаю всегда: русский и английский.\n🔊 Бот отвечает голосом, когда включён «Голос».",
        "en": "🎙 Voice messages always accepted: Russian and English.\n🔊 The bot replies with voice while «Voice» is on.",
    },
    "voice_on": {"ru": "🔊 Голос: Вкл", "en": "🔊 Voice: On"},
    "voice_off": {"ru": "🔊 Голос: Выкл", "en": "🔊 Voice: Off"},
    "btn_reset_progress": {"ru": "🗑 Сбросить прогресс", "en": "🗑 Reset progress"},
    "btn_about": {"ru": "ℹ️ О боте", "en": "ℹ️ About bot"},
    "btn_back": {"ru": "🔙 В главное меню", "en": "🔙 Back to menu"},
    "btn_language_ru": {"ru": "🇷🇺 RU ✓", "en": "🇷🇺 RU"},
    "btn_language_en": {"ru": "🇬🇧 EN", "en": "🇬🇧 EN ✓"},
    "voice_enabled": {"ru": "Голос включён!", "en": "Voice enabled!"},
    "voice_disabled": {"ru": "Голос выключен!", "en": "Voice disabled!"},
    "reset_confirm": {
        "ru": "⚠️ Нажми ещё раз для подтверждения. Прогресс будет удалён безвозвратно!",
        "en": "⚠️ Press again to confirm. Progress will be deleted permanently!",
    },
    "reset_done": {"ru": "🗑 Прогресс сброшен!", "en": "🗑 Progress reset!"},

    # === SCENARIOS ===
    "scenario_university": {
        "ru": "🎓 <b>Выбор вуза</b>\n\n"
              "Помогу выбрать вуз, разобраться с поступлением и специальностями.\n\n"
              "Что интересует?",
        "en": "🎓 <b>University</b>\n\n"
              "I'll help choose a university, understand admissions and majors.\n\n"
              "What interests you?",
    },
    "scenario_job": {
        "ru": "💼 <b>Поиск работы</b>\n\n"
              "Помогу подготовиться к собеседованию, составить резюме и найти стажировку.\n\n"
              "Что нужно?",
        "en": "💼 <b>Job Search</b>\n\n"
              "I'll help prepare for interviews, write a resume, and find an internship.\n\n"
              "What do you need?",
    },
    "scenario_adaptation": {
        "ru": "🤝 <b>Адаптация в компании</b>\n\n"
              "Помогу адаптироваться на новом месте, понять корпоративную культуру и общаться с коллегами.\n\n"
              "Начнём?",
        "en": "🤝 <b>Adaptation</b>\n\n"
              "I'll help you adapt to a new place, understand corporate culture, and communicate with colleagues.\n\n"
              "Shall we start?",
    },
    "choose_scenario": {"ru": "Выбери сценарий:", "en": "Choose a scenario:"},
    "btn_info_mode": {"ru": "📚 Информационный режим", "en": "📚 Info mode"},
    "btn_exam_mode": {"ru": "🎯 Режим экзаменатора", "en": "🎯 Examiner mode"},
    "btn_back_short": {"ru": "🔙 Назад", "en": "🔙 Back"},

    # === INFO MODE ===
    "info_header": {"ru": "📚 <b>Информационный режим</b>", "en": "📚 <b>Info mode</b>"},
    "info_ask_hint": {
        "ru": "✍️ Напиши свой вопрос — отвечу по теме.",
        "en": "✍️ Ask your question — I'll answer on topic.",
    },
    "info_continue": {
        "ru": "✍️ Продолжаем. Спроси что-нибудь ещё по этой теме.",
        "en": "✍️ Let's continue. Ask me anything else on this topic.",
    },
    "disclaimer": {
        "ru": "\n\n⚠️ Рекомендации носят информационный характер и не заменяют "
              "официальные требования вузов и работодателей. Не пишите боту личные данные "
              "(телефон, адрес, ФИО).",
        "en": "\n\n⚠️ Recommendations are for informational purposes only and do not replace "
              "official requirements of universities and employers. Do not share personal data "
              "(phone, address, full name) with the bot.",
    },

    # === EXAMINER ===
    "exam_header": {"ru": "🎯 <b>Режим экзаменатора</b>", "en": "🎯 <b>Examiner mode</b>"},
    "exam_intro": {
        "ru": "Предложу тебе проблемные задания.\nТы отвечаешь — я даю обратную связь.\n\nСколько заданий?",
        "en": "I'll give you practice tasks.\nYou answer — I give feedback.\n\nHow many tasks?",
    },
    "exam_cases_3": {"ru": "3 задания", "en": "3 tasks"},
    "exam_cases_5": {"ru": "5 заданий", "en": "5 tasks"},
    "exam_cases_10": {"ru": "10 заданий", "en": "10 tasks"},
    "exam_start": {"ru": "🎯 Начинаем! Генерирую {n} заданий...", "en": "🎯 Starting! Generating {n} tasks..."},
    "exam_loading": {"ru": "⏳ Подбираю задания…", "en": "⏳ Picking tasks…"},
    "exam_task": {"ru": "📋 <b>Задание {n} из {total}</b>", "en": "📋 <b>Task {n} of {total}</b>"},
    "exam_question": {"ru": "❓ <b>{text}</b>", "en": "❓ <b>{text}</b>"},
    "exam_score": {"ru": "📊 <b>Оценка: {n}/10</b>", "en": "📊 <b>Score: {n}/10</b>"},
    "exam_done": {"ru": "📋 Выполнено: {n}/{total}", "en": "📋 Completed: {n}/{total}"},
    "exam_complete": {"ru": "🎯 <b>Сессия завершена!</b>", "en": "🎯 <b>Session complete!</b>"},
    "exam_avg": {"ru": "Средний балл: {n}/10", "en": "Average score: {n}/10"},
    "exam_recommendations": {"ru": "<b>Рекомендации:</b>", "en": "<b>Recommendations:</b>"},
    "exam_next": {"ru": "▶ Следующее задание", "en": "▶ Next task"},
    "exam_results": {"ru": "📊 Результаты", "en": "📊 Results"},
    "exam_export": {"ru": "📥 Экспорт в PDF", "en": "📥 Export to PDF"},
    "exam_session_not_found": {"ru": "Сессия не найдена. Начни заново.", "en": "Session not found. Start over."},
    "exam_all_done": {"ru": "Все задания уже пройдены.", "en": "All tasks already completed."},
    "exam_not_choice": {"ru": "Это не задание с выбором", "en": "This is not a choice task"},
    "exam_correct": {"ru": "✅ Правильно! {text}", "en": "✅ Correct! {text}"},
    "exam_wrong": {
        "ru": "❌ Неправильно.\nТвой ответ: {your}\nПравильный: {correct}\n{text}",
        "en": "❌ Wrong.\nYour answer: {your}\nCorrect: {correct}\n{text}",
    },
    "exam_typical_errors": {"ru": "🔍 <b>Типичные ошибки:</b>", "en": "🔍 <b>Typical mistakes:</b>"},
    "exam_advice": {"ru": "💡 Совет: {text}", "en": "💡 Advice: {text}"},
    "info_sources": {"ru": "📚 <b>Источники</b>", "en": "📚 <b>Sources</b>"},
    "exam_strengths": {"ru": "✅ <b>Что сделано верно:</b>", "en": "✅ <b>What was done right:</b>"},
    "exam_weaknesses": {"ru": "⚠️ <b>Что можно улучшить:</b>", "en": "⚠️ <b>What can be improved:</b>"},
    "exam_example": {"ru": "💡 <b>Пример удачного ответа:</b>\n{text}", "en": "💡 <b>Example good answer:</b>\n{text}"},
    "exam_source": {"ru": "📚 <b>Источник:</b> {text}", "en": "📚 <b>Source:</b> {text}"},
    "exam_relevance_warning": {
        "ru": "⚠️ Твой ответ не совсем по теме задания.\nПричина: {reason}\n\n"
              "Попробуй ответить ещё раз или нажми «Следующее задание».",
        "en": "⚠️ Your answer is not quite on topic.\nReason: {reason}\n\n"
              "Try again or press «Next task».",
    },
    "exam_task_choice_text": {"ru": "Это задание с выбором ответа. Нажми на кнопку с вариантом.",
                              "en": "This is a choice task. Press the button with the option."},

    # === PROGRESS ===
    "progress_header": {"ru": "📊 <b>Твой прогресс</b>", "en": "📊 <b>Your progress</b>"},
    "progress_empty": {
        "ru": "Пока тут пусто — ты только начинаешь!\nПройди хотя бы одно задание, и покажу статистику.",
        "en": "Nothing here yet — you're just starting!\nComplete at least one task, and I'll show statistics.",
    },
    "progress_sessions": {"ru": "Всего сессий: {n}", "en": "Total sessions: {n}"},
    "progress_avg": {"ru": "Средний балл: {n}", "en": "Average score: {n}"},
    "progress_by_scenario": {"ru": "<b>По сценариям:</b>", "en": "<b>By scenario:</b>"},
    "progress_scenario_line": {"ru": "  {name}: {sessions} сессий, средний {avg}", "en": "  {name}: {sessions} sessions, avg {avg}"},
    "progress_reset_btn": {"ru": "🗑 Сбросить прогресс", "en": "🗑 Reset progress"},

    # === PDF EXPORT ===
    "pdf_generating": {"ru": "📥 Генерирую отчёт...", "en": "📥 Generating report..."},
    "pdf_no_results": {
        "ru": "📊 У тебя пока нет результатов.\nПройди хотя бы одно задание, чтобы я мог сгенерировать отчёт.",
        "en": "📊 No results yet.\nComplete at least one task so I can generate a report.",
    },
    "pdf_caption": {"ru": "📄 Отчёт: {scenario}", "en": "📄 Report: {scenario}"},
    "pdf_error": {"ru": "❌ Не удалось сгенерировать отчёт для {scenario}", "en": "❌ Failed to generate report for {scenario}"},
    "pdf_ready": {
        "ru": "✅ Отчёт готов!",
        "en": "✅ Report ready!",
    },

    # === VOICE ===
    "voice_error": {
        "ru": "🎤 Не удалось обработать голосовое сообщение.\nНапиши текстом — я обязательно отвечу!",
        "en": "🎤 Failed to process voice message.\nWrite text — I'll definitely answer!",
    },
    "voice_no_speech": {
        "ru": "🎤 Не удалось распознать речь.\nПопробуй говорить чётче или напиши текстом.",
        "en": "🎤 Failed to recognize speech.\nTry speaking clearer or write text.",
    },
    "voice_stt_error": {
        "ru": "🎤 Сервис распознавания речи недоступен.\nПопробуй позже или напиши текстом.",
        "en": "🎤 Speech recognition service is unavailable.\nTry again later or write text.",
    },
    "voice_text_prefix": {"ru": "📝 <b>Текст:</b>\n{text}", "en": "📝 <b>Text:</b>\n{text}"},

    # === ERRORS ===
    "error_general": {
        "ru": "❌ Что-то пошло не так. Попробуй позже или начни заново через /start",
        "en": "❌ Something went wrong. Try again later or restart via /start",
    },
    "error_general_short": {"ru": "❌ Ошибка", "en": "❌ Error"},
    "error_ai_overloaded": {
        "ru": "Извини, AI сейчас перегружен. Попробуй через минуту.",
        "en": "Sorry, AI is overloaded. Try again in a minute.",
    },

    # === COMMON MISTAKES (adaptive) ===
    "adaptive_no_weak": {
        "ru": "Отлично! У тебя нет слабых областей в этом сценарии.",
        "en": "Great! You have no weak areas in this scenario.",
    },
    "adaptive_clarify_question": {
        "ru": "🔎 <b>Уточняющий вопрос</b>\nПо теме «{friendly}» (кейс {case_id}, в среднем {score}) ты пока хромаешь. Давай разберёмся глубже: что именно было самым сложным и что ты теперь будешь делать иначе?",
        "en": "🔎 <b>Clarifying question</b>\nYou are weak on \"{friendly}\" (case {case_id}, average {score}). Let's dig deeper: what was the hardest part, and what will you do differently now?",
    },
    "adaptive_recommendation": {
        "ru": 'Задание «{case_id}» ({friendly}) — средний балл {score:.1f}, повтори его',
        "en": 'Task "{case_id}" ({friendly}) — avg score {score:.1f}, review it',
    },

    # === RAG ===
    "rag_relevant_info": {
        "ru": "Найденная релевантная информация:",
        "en": "Found relevant information:",
    },
    "rag_use_context": {
        "ru": "Используй найденную информацию для ответа. Если её недостаточно — скажи, что не знаешь.",
        "en": "Use the retrieved information to answer. If insufficient, say you don't know.",
    },
    "rag_no_context": {
        "ru": "Релевантной информации в базе нет. Ответь на основе своих знаний или скажи, что не знаешь.",
        "en": "No relevant information in the knowledge base. Answer from your knowledge or say you don't know.",
    },

    # === MISC ===

    # === INLINE MODE ===
    "inline_hint": {
        "ru": "Напиши запрос для поиска по базе знаний...",
        "en": "Type a query to search the knowledge base..."
    },
    "inline_search": {
        "ru": "Поиск по базе знаний",
        "en": "Search knowledge base"
    },
    "inline_not_found": {
        "ru": "Ничего не найдено по запросу: {query}",
        "en": "Nothing found for query: {query}"
    },
    "inline_not_found_title": {
        "ru": "Ничего не найдено",
        "en": "Nothing found"
    },
    "inline_open": {
        "ru": "Открыть",
        "en": "Open"
    },

    # === WELCOME MESSAGES (fallback for when prompt registry fails) ===
    "welcome_university": {
        "ru": "🎓 <b>Выбор вуза</b>\n\n"
              "Помогу выбрать вуз, разобраться с поступлением и специальностями.\n\n"
              "<b>Примеры вопросов:</b>\n"
              "• Какой вуз выбрать для IT?\n"
              "• Какие проходные баллы на МГУ?\n"
              "• Как подготовиться к ЕГЭ по информатике?",
        "en": "🎓 <b>University</b>\n\n"
              "I'll help choose a university, understand admissions and majors.\n\n"
              "<b>Example questions:</b>\n"
              "• Which university for IT?\n"
              "• What are the passing scores for MSU?\n"
              "• How to prepare for the CS exam?",
    },
    "welcome_job": {
        "ru": "💼 <b>Поиск работы</b>\n\n"
              "Помогу подготовиться к собеседованию, составить резюме и найти стажировку.\n\n"
              "<b>Примеры вопросов:</b>\n"
              "• Как написать резюме без опыта?\n"
              "• Как пройти собеседование в Яндекс?\n"
              "• Где искать стажировки?",
        "en": "💼 <b>Job Search</b>\n\n"
              "I'll help prepare for interviews, write a resume, and find an internship.\n\n"
              "<b>Example questions:</b>\n"
              "• How to write a resume with no experience?\n"
              "• How to pass a Yandex interview?\n"
              "• Where to find internships?",
    },
    "welcome_adaptation": {
        "ru": "🤝 <b>Адаптация в компании</b>\n\n"
              "Помогу адаптироваться на новом месте, понять корпоративную культуру и общаться с коллегами.\n\n"
              "<b>Примеры вопросов:</b>\n"
              "• Как попросить помощь у ментора?\n"
              "• Что делать, если не понимаешь задачу?\n"
              "• Как не выгореть в первый месяц?",
        "en": "🤝 <b>Adaptation</b>\n\n"
              "I'll help you adapt to a new place, understand corporate culture, and communicate with colleagues.\n\n"
              "<b>Example questions:</b>\n"
              "• How to ask a mentor for help?\n"
              "• What if I don't understand the task?\n"
              "• How not to burn out in the first month?",
    },
}


def t(key, lang="ru", **kwargs):
    # достаю строку по ключу, подставляю аргументы если есть
    if lang not in ("ru", "en"):
        lang = "ru"
    template = STRINGS.get(key, {}).get(lang) or STRINGS.get(key, {}).get("ru", key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
    return template

# падежные формы числительных: «1 задание», «3 задания», «5 заданий»

RU_NOUNS = {
    "task": ("задание", "задания", "заданий"),
    "session": ("сессия", "сессии", "сессий"),
    "question": ("вопрос", "вопроса", "вопросов"),
    "point": ("балл", "балла", "баллов"),
    "error": ("ошибка", "ошибки", "ошибок"),
    "case": ("кейс", "кейса", "кейсов"),
}

EN_NOUNS = {
    "task": ("task", "tasks"),
    "session": ("session", "sessions"),
    "question": ("question", "questions"),
    "point": ("point", "points"),
    "error": ("error", "errors"),
    "case": ("case", "cases"),
}


def plural_ru(n: int, one: str, few: str, many: str) -> str:
    # 1 задание, 2 задания, 5 заданий, но 11 заданий
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def noun(n: int, lang: str = "ru", key: str = "task") -> str:
    # слово в правильной форме: «3 задания», «5 заданий», «3 tasks»
    if lang == "en":
        one, many = EN_NOUNS.get(key, EN_NOUNS["task"])
        return one if abs(int(n)) == 1 else many
    one, few, many = RU_NOUNS.get(key, RU_NOUNS["task"])
    return plural_ru(n, one, few, many)

# варианты ответа тестовых заданий: llm любит писать их внутри вопроса или подставлять буквы

import re

LETTERS = ("A", "B", "C", "D")

# «Вариант A», «Ответ 1», просто буква — это не ответ, а заглушка
_PLACEHOLDER_RE = re.compile(r"^(?:вариант|option|ответ|answer)\s*[0-9a-dа-г]?$", re.IGNORECASE)
_LETTER_ONLY_RE = re.compile(r"^[A-DА-Г]$", re.IGNORECASE)

# маркер варианта: "A) ", "B. ", "C: " — в начале строки или после разделителя
_MARKER_RE = re.compile(r"(?:^|[\s(;:.,])([A-DА-Г])[\).:]\s*")

# кириллические двойники латинских букв
_LETTER_ALIASES = {"А": "A", "В": "B", "С": "C", "Д": "D"}


def clean_options(options) -> list[str]:
    # привести варианты к списку непустых строк
    if not isinstance(options, (list, tuple)):
        return []
    return [str(o).strip() for o in options]


def is_placeholder_options(options) -> bool:
    # битый список или заглушки вместо ответов — тест показывать нельзя
    opts = clean_options(options)
    if len(opts) != 4:
        return True
    if any(len(o) < 2 for o in opts):
        return True
    if any(_PLACEHOLDER_RE.match(o) or _LETTER_ONLY_RE.match(o) for o in opts):
        return True
    return len({o.casefold() for o in opts}) != 4


def split_lettered_options(text: str) -> tuple[str, list[str]]:
    # «A) 420 рублей; B) 360 рублей; …» → (текст вопроса без вариантов, 4 варианта)
    text = text or ""
    markers = list(_MARKER_RE.finditer(text))
    letters = [_LETTER_ALIASES.get(m.group(1).upper(), m.group(1).upper()) for m in markers]
    if letters != list(LETTERS):
        return text, []

    options = []
    for i, marker in enumerate(markers):
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        options.append(text[marker.end():end].strip(" \t\n;,.?"))

    if any(not o for o in options):
        return text, []
    head = text[:markers[0].start()].strip(" \t\n;,")
    return head, options


def clean_question(text: str) -> str:
    # лишние пробелы и двойные вопросительные знаки
    text = " ".join((text or "").split())
    return re.sub(r"\?{2,}", "?", text).strip()


def normalize_choice_case(case: dict) -> dict:
    # настоящие варианты в options, чистый вопрос; битый тест → обычный открытый вопрос
    case = dict(case or {})
    question, inline = split_lettered_options(case.get("question", ""))
    options = inline or clean_options(case.get("options"))

    if inline:
        case["question"] = clean_question(question)
    else:
        case["question"] = clean_question(case.get("question", ""))

    case["options"] = options
    if is_placeholder_options(options):
        case["type"] = "open"
    else:
        case["type"] = "choice"
        correct = case.get("correct")
        if isinstance(correct, bool) or not isinstance(correct, int) or not 0 <= correct < 4:
            case["correct"] = 0
    return case

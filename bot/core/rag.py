"""RAG-система — поиск релевантной информации по базе знаний.
сделал по гайду из интернета, TF-IDF + стемминг для русского.
работает нормально, но если будет время хочу попробовать chromadb"""

import logging
import re
import math
from collections import Counter
from bot.config import config

logger = logging.getLogger(__name__)

_documents = []  # тут все документы хранятся после загрузки
_doc_freq = {}  # word -> number of documents containing it
_total_docs = 0


def _load_documents() -> list:
    """Загрузить все markdown-файлы из data/"""
    global _documents, _doc_freq, _total_docs

    if _documents:
        return _documents

    data_dir = config.DATA_DIR
    if not data_dir.exists():
        logger.warning(f"Папка данных не найдена: {data_dir}")
        return []

    for subdir in ["universities", "companies", "interviews", "cases"]:
        subdir_path = data_dir / subdir
        if not subdir_path.exists():
            continue

        for md_file in subdir_path.glob("**/*.md"):
            try:
                try:
                    content = md_file.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    content = md_file.read_text(encoding="cp1251")
                chunks = _split_text(content, chunk_size=1000, overlap=200)
                for chunk in chunks:
                    _documents.append({
                        "content": chunk,
                        "source": str(md_file),
                        "source_type": subdir,
                    })
                logger.info(f"Загружен {md_file.name} ({len(chunks)} чанков)")
            except Exception as e:
                logger.error(f"Ошибка загрузки {md_file}: {e}")

    # Считаем document frequency (в скольких документах встречается слово)
    _total_docs = len(_documents)
    for doc in _documents:
        tokens = set(_tokenize(doc["content"]))
        for token in tokens:
            _doc_freq[token] = _doc_freq.get(token, 0) + 1

    logger.info(f"Всего загружено чанков: {_total_docs}")
    return _documents


def _split_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list:
    """Разбить текст на чанки"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start = end - overlap
    return chunks


# Простой стемминг для русского — обрезаем окончания
_RU_SUFFIXES = [
    "ость", "ение", "ание", "тель", "ество", "изм", "ист",
    "ый", "ий", "ой", "ые", "ие", "ий", "ая", "яя", "ое", "ее",
    "у", "ю", "а", "я", "о", "е", "ы", "и", "ь", "ий",
    "ться", "тся", "ться", "тся", "тся", "тся",
    "ться", "тся", "ться", "тся",
]


def _stem(word: str) -> str:
    """Упрощённый стемминг для русского"""
    # FIXME: это очень примитивный стемминг, для красивого русского надо бы
    #        использовать pymystem3 или natasha, но они тяжёлые
    if len(word) < 4:
        return word
    for suffix in _RU_SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[:-len(suffix)]
    return word


def _tokenize(text: str) -> list:
    """Токенизация + стемминг"""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    tokens = text.split()
    return [_stem(t) for t in tokens if len(t) > 2]


def _score(query_tokens: list, doc_tokens: list) -> float:
    """TF-IDF scoring с правильным IDF"""
    if not query_tokens or not doc_tokens:
        return 0.0

    score = 0.0
    doc_len = len(doc_tokens)
    doc_counter = Counter(doc_tokens)

    for token in query_tokens:
        if token in doc_counter:
            tf = doc_counter[token] / doc_len
            if _total_docs > 0:
                # IDF по корпусу: log(N / df)
                df = _doc_freq.get(token, 1)
                idf = math.log(_total_docs / df) if df > 0 else 0
            else:
                # Нет корпуса — IDF = log(всего слов / freq_in_doc)
                freq = doc_counter[token]
                idf = math.log(doc_len / freq) if freq > 0 else 0
            score += tf * idf

    return score


def search(query: str, k: int = 5, source_type: str = None) -> list:
    """Поиск по базе знаний (keyword-based)"""
    docs = _load_documents()
    if not docs:
        return []

    query_tokens = _tokenize(query)

    candidates = docs
    if source_type:
        candidates = [d for d in docs if d.get("source_type") == source_type]

    scored = []
    for doc in candidates:
        doc_tokens = _tokenize(doc["content"])
        s = _score(query_tokens, doc_tokens)
        if s > 0:
            scored.append((s, doc))

    scored.sort(key=lambda x: x[0], reverse=True)

    class SearchResult:
        def __init__(self, content, metadata):
            self.page_content = content
            self.metadata = metadata

    results = []
    for s, doc in scored[:k]:
        results.append(SearchResult(doc["content"], {"source": doc["source"], "source_type": doc["source_type"]}))

    return results


def rebuild_index():
    """Очистить кэш (для перезагрузки)"""
    global _documents, _doc_freq, _total_docs
    _documents = []
    _doc_freq = {}
    _total_docs = 0
    logger.info("Кэш документов очищен")

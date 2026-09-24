import pytest
from bot.core.rag import _tokenize, _score, _split_text, search, rebuild_index


def test_tokenize():
    """Тест токенизации текста"""
    tokens = _tokenize("Привет, мир! Это тест.")
    assert "привет" in tokens
    assert "мир" in tokens
    assert "тест" in tokens
    assert len(tokens) == 4


def test_split_text():
    """Тест разбиения текста на чанки"""
    text = "A" * 2500
    chunks = _split_text(text, chunk_size=1000, overlap=200)
    assert len(chunks) >= 2
    assert all(len(c) <= 1000 for c in chunks)


def test_split_text_short():
    """Тест короткого текста"""
    text = "Короткий текст"
    chunks = _split_text(text, chunk_size=1000, overlap=200)
    assert len(chunks) == 1


def test_score_same_tokens():
    """Тест скоринга с одинаковыми токенами"""
    query = ["python", "код"]
    doc = ["python", "код", "тест"]
    s = _score(query, doc)
    assert s > 0


def test_score_different_tokens():
    """Тест скоринга с разными токенами"""
    query = ["java"]
    doc = ["python", "код"]
    s = _score(query, doc)
    assert s == 0.0


def test_score_empty():
    """Тест скоринга с пустыми данными"""
    assert _score([], ["test"]) == 0.0
    assert _score(["test"], []) == 0.0
    assert _score([], []) == 0.0


def test_search_returns_results():
    """Поиск: непустой результат, скоринг по убыванию, все score > 0"""
    results = search("университет поступление", k=3)
    assert isinstance(results, list)
    assert len(results) > 0
    assert all(hasattr(r, "page_content") for r in results)
    assert all(r.metadata.get("source") for r in results)

    query_tokens = _tokenize("университет поступление")
    scores = [_score(query_tokens, _tokenize(r.page_content)) for r in results]
    assert scores[0] > 0
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_rebuild_index():
    """Тест очистки кэша"""
    await rebuild_index()
    from bot.core.rag import _documents
    assert len(_documents) == 0


def test_search_source_type_filter():
    """Фильтр source_type: только нужный тип, порядок скоринга сохранён"""
    results = search("стажировка компания", k=3, source_type="companies")
    assert isinstance(results, list)
    assert len(results) > 0
    assert all(r.metadata["source_type"] == "companies" for r in results)

    query_tokens = _tokenize("стажировка компания")
    scores = [_score(query_tokens, _tokenize(r.page_content)) for r in results]
    assert scores[0] > 0
    assert scores == sorted(scores, reverse=True)

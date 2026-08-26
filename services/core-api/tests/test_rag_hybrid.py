"""Phase 28: hybrid scoring + tokenization never raises, keyword score bounded."""

from app.rag.service import _keyword_score, _tokenize


def test_tokenize_basic():
    assert "hello" in _tokenize("Hello, world!")
    assert "http" not in _tokenize("a an the and for")  # stopwords filtered
    assert len(_tokenize("a " * 100)) <= 32


def test_tokenize_empty():
    assert _tokenize("") == []
    assert _tokenize("   ") == []


def test_keyword_score_exact_overlap():
    assert _keyword_score(["nexora", "rag"], "Nexora RAG hybrid search") == 1.0


def test_keyword_score_no_overlap():
    assert _keyword_score(["nexora"], "nothing relevant here") == 0.0


def test_keyword_score_partial():
    score = _keyword_score(["nexora", "rag", "hybrid"], "Nexora RAG")
    assert 0.0 < score < 1.0
    assert abs(score - 2 / 3) < 1e-6


def test_keyword_score_case_insensitive():
    assert _keyword_score(["nexora"], "NEXORA is great") == 1.0


def test_keyword_score_empty_query():
    assert _keyword_score([], "anything") == 0.0


def test_keyword_score_never_raises():
    assert isinstance(_keyword_score(["x"], None), float)  # type: ignore

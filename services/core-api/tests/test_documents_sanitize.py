"""Unit tests for upload filename sanitization + allowlists (§25)."""

from app.routers.documents import ALLOWED_CONTENT_TYPES, ALLOWED_EXTENSIONS, _sanitize_filename


def test_sanitize_keeps_simple_name():
    assert _sanitize_filename("report.pdf") == "report.pdf"


def test_sanitize_strips_path_traversal():
    name = _sanitize_filename("../../etc/passwd.csv")
    assert ".." not in name
    assert "/" not in name


def test_sanitize_replaces_unsafe_chars():
    name = _sanitize_filename('bad<>:"|?*.pdf')
    for ch in '<>:"|?*':
        assert ch not in name


def test_sanitize_empty_defaults():
    assert _sanitize_filename(None) == "document.pdf"
    assert _sanitize_filename("") == "document.pdf"


def test_sanitize_dots_only_name():
    assert _sanitize_filename("...") == "document.pdf"


def test_sanitize_length_cap():
    long = "a" * 400 + ".csv"
    assert len(_sanitize_filename(long)) <= 255


def test_allowlists_include_data_agent_types():
    assert {".pdf", ".csv", ".xlsx", ".xls", ".txt"} <= ALLOWED_EXTENSIONS
    assert "text/csv" in ALLOWED_CONTENT_TYPES
    assert "application/pdf" in ALLOWED_CONTENT_TYPES

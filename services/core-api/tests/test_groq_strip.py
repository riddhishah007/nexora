"""Unit tests for Groq <think> tag stripping."""

from app.llm.providers.groq import _strip_reasoning


def test_closed_think_block_removed():
    text = "<think>reasoning here</think>The answer is 4."
    assert _strip_reasoning(text) == "The answer is 4."


def test_unclosed_think_tag_tags_only():
    # Qwen truncation case: <think> without </think> — tags stripped, content kept
    text = "<think>partial reasoning without close\nAnswer continues."
    out = _strip_reasoning(text)
    assert "<think>" not in out
    assert "Answer continues." in out


def test_stray_close_tag_removed():
    text = "</think>\nJust the answer."
    assert _strip_reasoning(text) == "Just the answer."


def test_case_insensitive_and_multiline():
    text = "<THINK>\nline1\nline2\n</THINK>\n\nFinal."
    assert _strip_reasoning(text) == "Final."


def test_plain_text_untouched():
    assert _strip_reasoning("No tags here.") == "No tags here."

"""Unit tests for the stream-safe <think> chunk filter."""

import asyncio

from app.llm.providers.groq import filter_think_chunks


async def _collect(chunks: list[str]) -> str:
    async def gen():
        for c in chunks:
            yield c

    return "".join([c async for c in filter_think_chunks(gen())])


def test_no_think_passthrough():
    out = asyncio.run(_collect(["Hello", " world", "!"]))
    assert out == "Hello world!"


def test_think_block_dropped_across_chunks():
    chunks = ["<thi", "nk>hidden reasoning", "</thi", "nk>The answer", " is 4."]
    out = asyncio.run(_collect(chunks))
    assert out == "The answer is 4."
    assert "hidden" not in out


def test_split_opener_tag_detected():
    # "<think" split across two chunks must still trigger reasoning mode
    chunks = ["<", "think>secret stuff</think>", "visible"]
    out = asyncio.run(_collect(chunks))
    assert "secret" not in out
    assert "visible" in out


def test_unclosed_think_yields_tail_guard_content():
    # never closes: everything buffered inside is dropped, nothing crashes
    chunks = ["<think>partial..."] * 20
    out = asyncio.run(_collect(chunks))
    assert "<think" not in out


def test_stray_close_tag_only():
    out = asyncio.run(_collect(["</think>", "Answer."]))
    assert out == "Answer."

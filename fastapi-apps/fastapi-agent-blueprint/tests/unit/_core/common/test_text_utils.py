"""Unit tests for text chunking utilities (semantic-text-splitter wrapper)."""

from __future__ import annotations

from src._core.common.text_utils import chunk_text, chunk_text_by_tokens


class TestChunkText:
    def test_empty_string_returns_empty_list(self) -> None:
        assert chunk_text("") == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        assert chunk_text("   \n\t  ") == []

    def test_short_text_returns_single_chunk(self) -> None:
        result = chunk_text("Hello world.")
        assert result == ["Hello world."]

    def test_long_text_splits_into_multiple_chunks(self) -> None:
        text = "This is a sentence. " * 200  # ~4000 chars
        result = chunk_text(text, chunk_size=1000, overlap=100)
        assert len(result) > 1

    def test_chunks_respect_max_size(self) -> None:
        text = "word " * 500  # ~2500 chars
        result = chunk_text(text, chunk_size=1000, overlap=100)
        for chunk in result:
            assert len(chunk) <= 1000

    def test_chunks_have_overlap(self) -> None:
        # Use simple repeating text for predictable overlap
        text = "abcdefghij" * 50  # 500 chars
        result = chunk_text(text, chunk_size=100, overlap=20)
        assert len(result) > 1
        # Verify consecutive chunks share content
        for i in range(len(result) - 1):
            tail = result[i][-10:]
            assert tail in result[i + 1], (
                f"Expected overlap between chunk {i} and {i + 1}"
            )

    def test_custom_parameters(self) -> None:
        text = "Hello world. " * 100  # ~1300 chars
        result = chunk_text(text, chunk_size=200, overlap=30)
        assert len(result) > 1
        for chunk in result:
            assert len(chunk) <= 200


class TestChunkTextByTokens:
    def test_empty_string_returns_empty_list(self) -> None:
        assert chunk_text_by_tokens("") == []

    def test_short_text_returns_single_chunk(self) -> None:
        result = chunk_text_by_tokens("Hello world.")
        assert result == ["Hello world."]

    def test_long_text_splits_by_token_count(self) -> None:
        # ~200 tokens of text, split into chunks of max 50 tokens
        text = "The quick brown fox jumps over the lazy dog. " * 50
        result = chunk_text_by_tokens(text, max_tokens=50, overlap=10)
        assert len(result) > 1

    def test_custom_model_and_max_tokens(self) -> None:
        text = "Hello world. " * 500
        result = chunk_text_by_tokens(
            text, model="text-embedding-3-large", max_tokens=100, overlap=20
        )
        assert len(result) > 1

    def test_overlap_between_token_chunks(self) -> None:
        text = "word " * 500  # many tokens
        result = chunk_text_by_tokens(text, max_tokens=100, overlap=20)
        assert len(result) > 1
        # Verify consecutive chunks share some content
        for i in range(len(result) - 1):
            # Last few words of chunk i should appear in chunk i+1
            last_words = result[i].split()[-3:]
            overlap_text = " ".join(last_words)
            assert overlap_text in result[i + 1], (
                f"Expected token overlap between chunk {i} and {i + 1}"
            )

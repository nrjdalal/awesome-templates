from __future__ import annotations

from semantic_text_splitter import TextSplitter


def chunk_text(
    text: str,
    chunk_size: int = 1500,
    overlap: int = 200,
) -> list[str]:
    """문자 기반 텍스트 분할 (범용).

    내부적으로 Unicode word/sentence boundary를 인식하여
    의미 단위에서 분할을 시도한다.

    Args:
        text: 분할할 텍스트.
        chunk_size: chunk당 최대 문자 수 (기본 1500).
        overlap: 연속 chunk 간 겹침 문자 수 (기본 200).

    Returns:
        chunk 리스트. 빈 입력이면 ``[]``.
    """
    text = text.strip()
    if not text:
        return []
    splitter = TextSplitter(chunk_size, overlap=overlap)
    return splitter.chunks(text)


def chunk_text_by_tokens(
    text: str,
    model: str = "text-embedding-3-small",
    max_tokens: int = 8000,
    overlap: int = 200,
) -> list[str]:
    """토큰 기반 텍스트 분할 (임베딩 전처리용).

    tiktoken-rs 내장 — 별도 tiktoken 설치 불필요.
    임베딩 모델의 입력 토큰 제한(8,192)에 맞춰 분할할 때 사용.

    Args:
        text: 분할할 텍스트.
        model: tiktoken 모델명 (기본 "text-embedding-3-small").
        max_tokens: chunk당 최대 토큰 수 (기본 8000, 8192 제한에 여유 확보).
        overlap: 연속 chunk 간 겹침 토큰 수 (기본 200).

    Returns:
        chunk 리스트. 빈 입력이면 ``[]``.
    """
    text = text.strip()
    if not text:
        return []
    splitter = TextSplitter.from_tiktoken_model(model, max_tokens, overlap=overlap)
    return splitter.chunks(text)

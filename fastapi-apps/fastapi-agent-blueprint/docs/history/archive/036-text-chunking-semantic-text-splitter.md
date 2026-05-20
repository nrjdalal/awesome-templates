# 036. Text Chunking with semantic-text-splitter

- Status: Accepted
- Date: 2026-04-14
- Related issue: #69
- Related ADRs: [035](035-embedding-service-abstraction.md)(Embedding service)

## Summary

To provide text chunking infrastructure for embedding pipelines, we adopted `semantic-text-splitter` -- a zero-dependency Rust library with built-in tiktoken-rs -- over LangChain's `RecursiveCharacterTextSplitter`, a custom implementation, or other alternatives. The library is wrapped in thin utility functions in `_core/common/text_utils.py`.

## Background

- **Trigger**: The embedding service abstraction (ADR 035) provides `embed_text` and `embed_batch`, but long documents exceed embedding model input limits (8,192 tokens for both OpenAI and Bedrock Titan). A text chunking utility is needed as the preprocessing step before embedding.

- **Decision type**: Upfront design with course correction -- the initial implementation was a custom 60-line function (`chunk_text`) with character-based splitting. Review revealed that (1) character-based splitting doesn't align with token-based model limits, and (2) established libraries handle Unicode edge cases that custom code misses. The implementation was replaced with `semantic-text-splitter` before merge.

### The Chunking Pipeline

```
Long Document
    → chunk_text_by_tokens(text, model, max_tokens=8000)   ← this ADR
    → embed_batch(chunks)                                   ← ADR 035
    → vector_store.upsert(vectors)                          ← ADR 034
```

Text chunking is the first step. It must produce chunks that respect the embedding model's token limit while preserving semantic coherence.

## Problem

### 1. Embedding models have strict input limits

| Model | Max Tokens/Input | What Happens on Exceed |
|-------|-----------------|----------------------|
| OpenAI text-embedding-3-small | 8,192 | API returns 400 error |
| OpenAI text-embedding-3-large | 8,192 | API returns 400 error |
| Bedrock Titan v2 | 8,192 tokens / 50,000 chars | API returns ValidationException |

Documents routinely exceed these limits. A 10-page PDF can contain 50,000+ characters (~12,000 tokens). Without chunking, embedding fails.

### 2. Character-based splitting misaligns with token limits

The initial custom implementation split by character count (1,500 chars). But the token-to-character ratio varies significantly:

| Language | Avg chars/token | 1,500 chars ≈ |
|----------|----------------|---------------|
| English | ~4 | ~375 tokens |
| Korean | ~1.5 | ~1,000 tokens |
| Code | ~3 | ~500 tokens |

A 1,500-char chunk of Korean text uses ~2.7x more tokens than English. Character-based splitting provides no guarantee that chunks fit within token limits.

### 3. Edge cases in text splitting

Custom implementations commonly miss:
- **CJK text**: No spaces between words; splitting on whitespace is meaningless
- **Abbreviations**: "Dr. Smith went to Washington." -- splitting on ". " breaks "Dr."
- **Multi-byte UTF-8**: Slicing by byte index can split characters mid-sequence
- **Markdown structure**: Headers, code blocks, and lists need boundary awareness

## Alternatives Considered

### A. langchain-text-splitters (RecursiveCharacterTextSplitter)

The de facto standard by download count (~29M monthly downloads). Provides `RecursiveCharacterTextSplitter` with `from_tiktoken_encoder()` for token-aware splitting.

**Rejected**: Pulls in 10 transitive packages including `langchain-core` and `langsmith`. The project already rejected LangChain for embeddings (ADR 035) and VectorStore (ADR 034). Adding `langchain-text-splitters` for chunking while deliberately avoiding LangChain elsewhere creates an inconsistency. The download count is inflated by LangChain framework users who install it transitively.

### B. Custom implementation (tried and replaced)

A 60-line function with character-based splitting and sentence boundary detection via regex (`[.!?]\s`).

**Replaced**: (1) Character-based splitting doesn't align with token-based model limits (see Problem #2). (2) Regex-based sentence detection fails on abbreviations, URLs, and non-Latin scripts. (3) No Unicode word/sentence boundary awareness (UAX #29). The function worked for English-only tests but would fail in production with multilingual content.

### C. chonkie

Newer library (3,900 GitHub stars) with async support and diverse chunking strategies.

**Rejected**: Requires `numpy>=2.0` and `huggingface-hub` as mandatory dependencies -- contradicts the project's dependency minimalism. The `numpy` requirement alone adds a heavy compiled dependency for what is fundamentally string processing.

### D. semchunk

Battle-tested (used by IBM Docling, Microsoft Intelligence Toolkit) with highest RAG quality in benchmarks.

**Rejected**: Requires `mpire` (multiprocessing library) with `dill` and `pygments` as dependencies. The fork-based multiprocessing model conflicts with FastAPI's asyncio event loop. Appropriate for batch document processing pipelines but overkill for a utility function.

### E. semantic-text-splitter (chosen)

Rust-compiled library with zero Python runtime dependencies. tiktoken-rs is compiled into the binary wheel.

## Decision

### 1. semantic-text-splitter as core dependency

```toml
dependencies = [
    ...
    "semantic-text-splitter>=0.17.0",
]
```

Added to core (not optional) because text chunking is provider-agnostic -- it's needed regardless of whether OpenAI or Bedrock is the embedding provider. The package adds zero Python transitive dependencies (single Rust binary wheel, ~8MB).

### 2. Two utility functions in _core/common/text_utils.py

```python
def chunk_text(text, chunk_size=1500, overlap=200) -> list[str]
```
Character-based splitting for general purposes (logging, summarization, display).

```python
def chunk_text_by_tokens(text, model="text-embedding-3-small", max_tokens=8000, overlap=200) -> list[str]
```
Token-based splitting for embedding preprocessing. Uses tiktoken-rs internally (no `tiktoken` Python package needed). Default `max_tokens=8000` provides 192-token safety margin below the 8,192 limit.

### 3. Thin wrapper, not direct usage

Domain code calls `chunk_text_by_tokens()`, not `TextSplitter.from_tiktoken_model()` directly. This provides:
- Consistent empty-string handling (`[]` for blank input)
- A stable API if the underlying library is ever replaced
- Discoverability (utility functions in `_core/common/`, not scattered library imports)

### 4. semantic-text-splitter handles boundaries internally

The library uses Unicode Text Segmentation (UAX #29) at the Rust level:
1. Characters
2. Grapheme cluster boundaries
3. Word boundaries
4. Sentence boundaries
5. Line breaks
6. Paragraphs

This covers CJK, abbreviations, and multi-byte characters without project-specific regex.

## Rationale

### Why Zero Dependencies Matters

| Library | Added Python Packages | Token-aware |
|---------|----------------------|-------------|
| langchain-text-splitters | 10 (langchain-core, langsmith, ...) | Via tiktoken |
| chonkie | 5+ (numpy, huggingface-hub, ...) | Via tiktoken |
| semchunk | 5+ (mpire, dill, pygments, ...) | Via tiktoken |
| **semantic-text-splitter** | **0** | **Built-in (tiktoken-rs)** |
| Custom implementation | 0 | Must add tiktoken |

`semantic-text-splitter` is the only option that provides token-aware splitting with zero additional Python dependencies. The tiktoken-rs tokenizer is compiled into the Rust binary, eliminating the need for the `tiktoken` Python package for chunking purposes.

Note: `tiktoken` (Python) is still in `[openai]` optional extras for a different purpose -- the OpenAI embedding client uses it for API request batching (300K token limit enforcement). These are separate concerns.

### The RecursiveCharacterTextSplitter Concept is Standard, Not the Package

The investigation revealed an important distinction: `RecursiveCharacterTextSplitter`'s *strategy* (try paragraph breaks, then sentence breaks, then word breaks, then characters) is the industry standard. The `langchain-text-splitters` *package* is popular because it's installed transitively with LangChain. Projects moving away from LangChain (to PydanticAI, CrewAI, direct SDK usage) do not retain the package.

`semantic-text-splitter` implements the same hierarchical splitting strategy (Unicode sentence > word > grapheme > character) without the LangChain dependency tree.

### Trade-offs Accepted

- **0.x version**: `semantic-text-splitter` is at v0.29.0 (not yet 1.0). Mitigated by 73 releases, 1,190 commits, and active maintenance. The overlap feature has been stable since v0.12.2 (April 2024).
- **Rust binary wheel**: Requires platform-specific wheels. Pre-built wheels exist for Linux x86_64/aarch64, macOS x86_64/ARM64, and Windows x86_64. Rare platforms may need Rust toolchain for compilation.
- **No async API**: The library is synchronous (pure CPU computation in Rust). This is acceptable -- text splitting completes in microseconds, faster than the overhead of an async context switch.

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?

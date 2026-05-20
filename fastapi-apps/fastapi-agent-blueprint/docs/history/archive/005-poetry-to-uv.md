# 005. Migration from Poetry to uv

- Status: Accepted
- Date: 2025-04-16
- Related issue: #3
- Related PR: #4
- Related commit: `de6e063`

## Summary

To unify Python version management and package management into a single tool with faster dependency resolution, we migrated from pyenv + Poetry to uv.

## Background

- **Trigger**: Environment setup required two separate tools (pyenv + Poetry) with independent configurations, and Poetry's dependency resolution speed was noticeably degrading as dependencies grew.
- **Decision type**: External factor — uv emerged as a mature Rust-based alternative that unified both concerns.

Python version management and package management were being performed with separate tools.

- **Python version management**: pyenv
- **Package management**: Poetry

Both tools had to be installed, configured, and maintained separately,
and new team members needed to install and integrate pyenv and Poetry individually when setting up their environment.

## Problem

### 1. Tool Fragmentation

A dual-tool system was used: pyenv for installing Python versions and Poetry for managing virtual environments and dependencies.
The two tools' configurations were independent of each other, requiring coordination work
such as recreating the Poetry virtual environment when the Python version changed.

### 2. Speed

Poetry's dependency resolution and lock file generation were slow.
As dependencies grew, `poetry lock` execution time became noticeably longer.

## Alternatives Considered

### A. Keep Poetry + pyenv
- Pros: Already familiar, mature ecosystem
- Cons: Continued pyenv dependency, slow dependency resolution, two tools to maintain

### B. uv (chosen)
- Rust-based dependency resolution 10-100x faster than Poetry
- Unifies Python version management (`uv python install`) and package management in a single tool
- Uses `pyproject.toml` PEP standard format (no Poetry-specific `[tool.poetry]` section needed)

## Decision

**Adopt uv**

```toml
# Before (Poetry) — pyproject.toml
[build-system]
requires = ["poetry-core>=2.0.0,<3.0.0"]
build-backend = "poetry.core.masonry.api"

[project]
dependencies = [
    "fastapi (>=0.115.8,<0.116.0)",  # Poetry-specific version notation
    ...
]
```

```toml
# After (uv) — pyproject.toml
[project]
requires-python = ">=3.12.8"
dependencies = [
    "fastapi>=0.115.12",  # PEP 508 standard notation
    ...
]
# build-system section removed
```

- Lock file size reduced by approximately 45%: `poetry.lock` (1,248 lines) -> `uv.lock` (685 lines)

## Rationale

| Criteria | Poetry + pyenv | uv |
|----------|---------------|-----|
| Python version management | Requires separate pyenv | Unified with `uv python install` |
| Dependency resolution speed | Slow | Rust-based, 10-100x faster |
| Tool installation | 2 tools: pyenv + Poetry | 1 tool: uv |
| pyproject.toml format | Contains Poetry-specific syntax | PEP standard compliant |
| Lock file size | 1,248 lines | 685 lines |

1. Managing Python versions and packages with a single tool simplifies environment setup
2. Dependency resolution speed is noticeably faster, improving the development experience
3. Using the PEP standard `pyproject.toml` format reduces tool dependency

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?

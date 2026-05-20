# 012. Consolidating pre-commit Linting Tools: Migration to Ruff

- Status: Accepted
- Date: 2026-03-23
- Related Issues: #58
- Related ADRs: 010-code-quality-tools.md (Supersedes)

## Summary

To consolidate 6 separate linting tools into one with faster execution and centralized configuration, we replaced the entire pre-commit linting stack with Ruff.

## Background

- **Trigger**: 6 linting tools running sequentially made pre-commit slow, configurations were scattered across `.pre-commit-config.yaml` args, and Python version hardcoding in Black caused breakage when upgrading to Python 3.13.
- **Decision type**: External factor — Ruff matured to the point where it could replace all 6 tools with a single Rust-based binary (adopted by FastAPI, Pydantic, Django, etc.).

In ADR 010, the pre-commit configuration was systematized with a combination of 6 tools:
pyupgrade, autoflake, isort, Black, flake8 + plugins, bandit.

Each tool ran in its own virtualenv, and version compatibility and settings management were scattered across tools.

## Problem

### 1. Execution Speed

6 tools ran sequentially, each maintaining a separate virtualenv.
Initial installation took several minutes, and sequential per-tool execution made the overall pre-commit time long.

### 2. Scattered Configuration

Each tool's settings were scattered inline in the `args` of `.pre-commit-config.yaml`:

```yaml
# flake8 settings compressed into a single args line
args:
  - --ignore=F841,E501,W503,E203,E402,F401,B008,B006,C901,SIM114,SIM910,SIM904,E704
  - --max-line-length=88
  - --max-complexity=20
  - --per-file-ignores=**/routers/*:B008,**/workflows/*:B006
```

Without centralized management in `pyproject.toml`, finding settings required reading `.pre-commit-config.yaml`.

### 3. Version Management Burden

6 tools required individual `rev` management.
Running `pre-commit autoupdate` could introduce compatibility issues between tools.

### 4. Python Version Dependency

The Black hook had `language_version: python3.12` hardcoded,
causing the hook to fail when upgrading to Python 3.13.

## Alternatives Considered

### A. Maintain Status Quo (6 tools)
- Stable and proven
- Disadvantage: The 4 problems listed above persist

### B. Consolidate with Ruff (chosen)
- Rust-based, 10-100x faster execution speed
- Consolidates flake8, pyupgrade, autoflake, isort, Black, and bandit rules into one
- Centralized configuration management in `pyproject.toml`
- Only 1 rev to manage

### C. Partial Migration (only replace flake8 with Ruff)
- Keep Black/isort and only replace flake8
- Disadvantage: The number of tools does not decrease, so the fundamental problem remains unsolved

## Decision

**Replaced all 6 linting tools with a single Ruff installation**

### Removed Tools

| Tool | Ruff Replacement Rule |
|------|----------------------|
| pyupgrade | `UP` (Python 3.12+ syntax modernization) |
| autoflake | `F` (unused import/variable removal) |
| isort | `I` (import sorting) |
| Black | `ruff format` (Black-compatible formatting) |
| flake8 + bugbear + comprehensions | `E`, `W`, `F`, `B`, `C4` |
| bandit | `S` (security checks) |

### Retained Tools

- **pre-commit-hooks**: General file validation (trailing whitespace, etc.)
- **mypy**: Type checking (an area Ruff does not cover)
- **Custom pygrep hooks**: 4 architecture violation checks

### Configuration Structure

```toml
# pyproject.toml -- centralized management
[tool.ruff]
target-version = "py312"
line-length = 88
exclude = ["migrations"]

[tool.ruff.lint]
select = ["E", "W", "F", "UP", "I", "B", "C4", "SIM", "S"]
ignore = [...]  # 1:1 mapping from existing flake8 ignore list
```

```yaml
# .pre-commit-config.yaml -- handles execution only
- repo: https://github.com/astral-sh/ruff-pre-commit
  rev: v0.15.7
  hooks:
    - id: ruff-check
      args: [--fix]
    - id: ruff-format
```

### Rule Mapping

Existing flake8 ignore lists were mapped 1:1 to Ruff codes.
Rules that do not exist in Ruff (W503, E203, E704, SIM904) were removed.
New rules not caught by the existing tools (SIM102, SIM117, B904, UP046, S607)
were added to the ignore list for behavioral consistency.

## Rationale

| Criterion | 6 Tools (before) | Ruff (current) |
|-----------|-----------------|----------------|
| Execution speed | Sequential 6-pass execution | Rust-based, 10-100x faster |
| Settings location | .pre-commit-config.yaml args | Centralized in pyproject.toml |
| Version management | 6 individual revs | 1 rev |
| Python version | Hardcoding required for Black | Declarative management via target-version |
| Rule compatibility | flake8 code system | Same code system maintained |

1. Improved developer experience: pre-commit execution time noticeably reduced
2. Settings readability: All linting rules visible in a single `pyproject.toml` location
3. Simplified maintenance: Only 1 tool version to manage
4. Ecosystem trend: Ruff is establishing itself as the Python linting standard (adopted by major projects including FastAPI, Pydantic, Django, etc.)

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?

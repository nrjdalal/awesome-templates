# 021. Architecture Governance via Pre-commit Hooks and CI

- Status: Accepted
- Date: 2026-03 ~ 2026-04
- Related issue: #30, #39
- Related ADR: [010](010-code-quality-tools.md)(Code Quality Tools), [012](012-ruff-migration.md)(Ruff Migration), [020](020-aidd-skills-governance.md)(AIDD Skills Governance)

## Summary

To enforce architectural rules at commit time rather than code review time, we implemented custom pre-commit hooks (domain-to-infrastructure import prohibition, entity pattern detection) and a CI architecture job — shifting governance from "manual review" to "automated enforcement."

## Background

- **Trigger**: After establishing layer rules (Domain must not import Infrastructure — ADR 006) and pattern prohibitions (no Entity pattern — ADR 004), violations were occasionally introduced by AI-assisted development and missed during code review. The rules were documented in CLAUDE.md but documentation alone could not prevent violations.
- **Decision type**: Experience-based correction — violations in code review revealed that documentation-based enforcement was insufficient.

ADR 010/012 had already established code quality tools (Ruff for linting and formatting). However, Ruff enforces Python style and best practices — it does not understand project-specific architectural rules like "Domain layer must not import from Infrastructure layer."

## Problem

### 1. Architectural Rule Violations Slip Through

`CLAUDE.md` states "No Infrastructure imports from the Domain layer." But neither Ruff nor Python's type system can detect `from src.user.infrastructure.repositories import UserRepository` inside a domain file.

### 2. Pattern Resurrection

ADR 004 deprecated the Entity pattern. But new developers (or AI sessions) unfamiliar with this history occasionally re-introduce `.to_entity()`, `.from_entity()`, or `_core.domain.entities` imports.

### 3. Inconsistent Commit Messages

Without validation, commit messages varied between Korean/English, arbitrary formats, and missing context — making `git log` unusable for understanding changes.

### 4. Reactive vs Proactive

Code review catches violations after the developer has written the code. For architectural rules that should never be violated, the feedback should come immediately at commit time.

## Alternatives Considered

### A. Code Review Only

Rely on human reviewers to catch architectural violations during PR review.

Rejected: Reactive — developers invest time in wrong implementations before receiving feedback. Not reliable when reviewers miss subtle violations or when PRs are large. Cannot enforce consistency across AI-assisted development sessions.

### B. Custom Python Linter Plugin

Write custom Ruff or flake8 rules for architectural violations.

Rejected: Over-engineered for string-pattern-based rules. Writing an AST-based linter plugin for "file X must not import from path Y" is more complex than a regex pattern match. Pygrep hooks achieve the same result with 1 line each.

### C. Architecture Tests (e.g., ArchUnit style)

Write runtime tests that check import dependencies between modules.

Rejected: Tests run after code is written, not at commit time. Adds test execution overhead. The pre-commit approach gives immediate feedback during the developer's workflow, not after they've pushed.

## Decision

### Architectural Hooks (pre-commit, commit stage)

Two custom pygrep hooks enforce architecture rules at commit time:

```yaml
# 1. Prohibit Domain → Infrastructure import
- id: no-domain-infra-import
  name: "Prohibit Domain → Infrastructure import"
  language: pygrep
  entry: "from src\\..*\\.infrastructure"
  files: "src/.*/domain/.*\\.py$"

# 2. Detect residual Entity pattern (ADR 004)
- id: no-entity-pattern
  name: "Entity pattern not allowed (unified to DTO)"
  language: pygrep
  entry: "\\.to_entity\\(|\\.from_entity\\(|from src\\._core\\.domain\\.entities"
  files: "\\.py$"
```

### Commit Message Validation (commit-msg stage)

Conventional Commits enforced via `conventional-pre-commit`:

```yaml
- id: conventional-pre-commit
  stages: [commit-msg]
  args: [feat, fix, refactor, docs, chore, test, ci, perf, style, i18n]
```

### CI Architecture Job

A dedicated `architecture` job in GitHub Actions runs all pre-commit hooks on the full codebase:

```yaml
architecture:
  runs-on: ubuntu-latest
  steps:
    - name: Run architecture checks
      run: uv run pre-commit run --all-files
```

This catches violations that local pre-commit might miss (e.g., if a developer hasn't installed hooks).

### Claude Code Harness Hooks

Additional enforcement for AI-assisted development in `.claude/settings.json`:

- `PreToolUse` hook: `pre-tool-security.sh` runs before every Edit/Write/Bash operation
- `Stop` hook: `stop-sync-reminder.sh` reminds to check guideline sync when the AI finishes work

## Rationale

| Decision | Reason |
|----------|--------|
| Pygrep over custom linter | Regex-based detection is sufficient for import path and method name patterns. Zero build overhead, zero dependencies |
| Pre-commit over runtime tests | Immediate feedback at commit time. Developers see violations before creating a PR |
| CI `architecture` job | Safety net for developers who skip local pre-commit hooks. Runs on every PR to main |
| Conventional Commits | Structured commit messages enable `git log` filtering, automated changelog generation, and semantic versioning |
| Separate from Ruff | Ruff handles Python-generic quality (style, best practices). Architectural hooks handle project-specific rules. Different concerns, different tools |
| Claude Code harness hooks | AI-assisted development needs the same governance as human development. Harness hooks enforce rules during AI sessions |

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?

> Historical appendices A/C from `docs/ai/shared/target-operating-model.md` at cd5e6b5.
> Appendix B remains live in the operating model.

## Appendix A — Eight Workstreams from Issue #117

| Workstream | Where it lives in this model | Phase |
|---|---|---|
| `asset-triage` | [harness-asset-matrix.md](../../../ai/shared/harness-asset-matrix.md) | 0 (this PR) |
| `default-flow` | §1, `AGENTS.md` § Default Coding Flow | 1 (this PR) |
| `verification-first` | §1 `verify` step; Codex R7 adapter spec in §5 | 3 |
| `self-review` | §1 `self-review` step | 1 (skill body) → 4 (hook) |
| `completion-gate` | §1 `completion gate` step | 4 |
| `exception-model` | §3 | 1 (vocabulary defined) → 2 (parser) |
| `cross-tool-consistency` | §5 + Phase 5 shared module | 1 (precedence) → 5 (consolidation) |
| `migration-path` | [migration-strategy.md](../../../ai/shared/migration-strategy.md) | 0 (this PR) |

## Appendix C — Eight Design Questions (issue #117) — Resolution Pointers

Detailed answers live in [ADR 045 §Eight Design Questions](../../045-hybrid-harness-target-architecture.md#eight-design-questions-issue-117--resolution-map). The pointers below name the canonical section of this document.

1. Project-specific value vs commodity scaffolding → harness-asset-matrix.md Tier classification.
2. Stay local / overlay / replace / drop → matrix bucket column.
3. Minimum viable process governor → §1 + §3.
4. Mandatory by default for coding work → §2.
5. Where enforcement lives → §5 ("Where enforcement lives" table).
6. Valid exception → §3.
7. Claude / Codex / Antigravity alignment → §5.
8. Rigor without friction → §1 (mandatory subset) + §3 (escape lanes) + §7 (model identity).

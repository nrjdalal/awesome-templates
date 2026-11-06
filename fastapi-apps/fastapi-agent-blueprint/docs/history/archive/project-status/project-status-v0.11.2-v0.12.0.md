# Project Status — v0.11.2 → v0.12.0

Rows archived from `.claude/rules/project-status.md` when v0.12.0 shipped
(2026-11-07), following the release archive rule in
[`sync-guidelines.md`](../../../ai/shared/skills/sync-guidelines.md).
Narrative for these changes lives in `CHANGELOG.md` under `[0.12.0]`.

| Feature | Issue | Impact |
|---------|-------|--------|
| ADR decision evidence | #414, #427 | Scoped clauses, applicability and current proof flow through existing artifacts (ADR 064/065). |
| Runtime verify and content heuristics retired | #414 | Verify-first reminders/logs and pre-edit heuristics removed; blocking `sensitive-logging` hook and generated harness inventory added (ADR 061–063). |
| Ticket sessions and review packets | #427 | Native ticket briefs, fresh serial sessions and review packets with a path/size risk floor and one P0/P1 cross-vendor round (ADR 060). |
| Context budgets and skill routing | #413, #415–#420, #426 | Compact tracked context, preserve routing in TOM, and block byte regrowth (ADR 059). |

# Harness Asset Matrix

This is the on-demand navigator for the native harness inventory.
[ADR 062](../../history/062-generated-harness-inventory.md) replaces manual rows,
counts, and repeated role descriptions with a reproducible inventory. Historical
per-asset rationale remains in the [frozen manual matrix](../../history/archive/harness-asset-matrix-2026-11-06.md).
Current behavior and policy come from code, ADRs, and the linked shared procedures.

- [Generated inventory](harness-inventory.csv): tier, logical asset, bucket,
  tracked/local-only/retired status, and skill-triple members.
- [Reviewed bucket map](harness-buckets.json): committed path-to-bucket decisions
  and the original inventory tier for each retired path. Buckets are judgments;
  the generator never infers them from a path or a governor Tier A/B/C.
- Generator: `python3 tools/generate_harness_inventory.py`; validate with
  `python3 tools/generate_harness_inventory.py --check`.

## Bucket Definitions

| Bucket | Meaning |
|---|---|
| Keep | Project-specific architecture, safety, or reference value |
| Overlay | Generic process discipline routed through the Default Coding Flow |
| Replace | Existing asset deliberately superseded by another mechanism |
| Drop | Removed asset, retained as a historical decision; no active callers |

Do not equate bucket assignment with demonstrated error-rate reduction. Old matrix
High/Medium/Low impact labels are historical judgments, not measurements.

## Tier 0 — Constitutional Assets

Fixed tool entry points, the PR/ticket forms, and ADR 045. The exact list lives in
`CONSTITUTIONAL` in the generator. `.claude/settings.local.json` is a declared
optional local-only row; its presence and contents never affect generated output.
Other ADRs remain indexed by the [history index](../../history/README.md).

## Tier 1 — Shared Reference and Enforcement Layer

Tracked `docs/ai/shared/*.md`, the shared governor package, the closed governor
review archive, and named enforcement tools. Package/archive groups each count
once. Supporting JSON/CSV data is owned by this navigator, not recursively scanned
as another inventory. Frozen matrix snapshots are outside the discovery scope.

## Tier 2 — Skills (3-Layer Hybrid C)

One row per skill triple: shared procedure plus Claude and Codex wrappers. The
three file sets must be complete and have the same reviewed bucket. The generated
row lists every member; new skills automatically enter discovery and require a
bucket decision for each path. Skill phases and routing are defined by the
[operating model](target-operating-model.md), not inventory role prose.

## Tier 3 — Hooks

All tracked files under `.claude/hooks/`, `.codex/hooks/`, `.antigravity/hooks/`,
excluding `__pycache__` and `.pyc`. Removal requires retiring the reviewed path
explicitly and verifying consumers; a missing active map path blocks the gate.

## Tier 4 — Rule Files

Tracked `.claude/rules/*.md`, `.codex/rules/*`, and `.antigravity/rules/*.md`.
These inventory tiers come from the former matrix Verification scope. They are
unrelated to the governor-changing review tiers in governor-paths.md.

## Bucket Distribution Summary

Run the check command for current counts, or filter the generated CSV. Exclude the
local-only row from tracked bucket shares; include historical Drop rows when
comparing the original bucket distribution. Active tracked count excludes retired
rows too. No current count, percentage, line count, or stability label is copied
into this file. The intended model remains Mostly Local with Philosophy Overlay.

## Verification

The blocking pre-commit and CI checks assert generated output equals the committed
CSV, reviewed bucket keys equal discovered assets plus explicit retirements, skill
triples are complete, and retired assets are absent from the git index. Unknown
or stale judgments fail rather than inheriting a bucket from a glob.

When assets change: stage new/deleted files, review bucket decisions, regenerate,
then stage the map and CSV. Review a Drop transition for callers across all three
adapters; generated absence does not prove zero callers. Restore the caller or
replacement gate with the asset on rollback. Do not update the frozen archive.

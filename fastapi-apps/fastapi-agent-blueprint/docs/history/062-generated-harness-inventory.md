# 062. Generated Harness Inventory

- Status: Accepted
- Date: 2026-11-06
- Issue: #414 B3
- Refines ADR [045](045-hybrid-harness-target-architecture.md) asset inventory ownership.

## Problem

The manual matrix repeats code-derived roles and keeps counts by hand. The audit
identified an 84 KB reference read during sync. New ticket skills also exposed
stale prose/counts despite correct quick-table rows. A shorter manual table would
retain the same regeneration problem; governor-path review tiers do not describe
inventory membership and cannot replace its discovery scope.

## Alternatives

1. Keep editing the full matrix: preserves rationale inline, with repeated drift.
2. Derive buckets from path globs: small, but confuses discovery with judgment.
3. Generate membership/counts, commit bucket judgments, and preserve rationale once
   in a frozen archive: adds one deterministic tool but removes manual repetition.

## Decision

Choose option 3. The [navigator](../ai/shared/harness-asset-matrix.md) keeps stable
inbound anchors and links to a generated CSV and a reviewed path-to-bucket JSON map.
Discovery follows the old matrix Verification block: named constitutional assets,
shared root Markdown plus named groups/tools, complete skill triples, hook files,
and rule globs. The named enforcement set includes the existing Governor Footer
checker plus the context-budget checker (ADR 059), review-packet reporter (ADR 060),
and this inventory generator. These explicit additions extend the old scope;
other policing tools are not implicitly included merely because they live in tools/.
It never imports governor review-tier globs.

Inventory uses git-tracked paths, including staged additions/deletions. Local-only
settings are a fixed optional row and do not reveal presence or private contents.
Package and closed-review-archive groups count once; the old matrix archive and
supporting data do not recursively enter discovery. A skill triple counts once,
but every member needs the same explicit bucket judgment.

A blocking pre-commit check and CI compare generated output with the committed CSV.
Unmapped new assets, stale map entries, missing triple members, invalid buckets,
and retired paths still tracked fail the gate. Humans still review bucket choices
and verify zero callers before retirement; absence alone does not prove safe removal.

## Consequences

- **ADR062-G1:** Scope discovery and bucket judgments have distinct sources. No
  default bucket or generated judgment may silently classify a new path.
- **ADR062-G2:** Preserve complete skill triples and compare generated==committed.
  Track explicit retirements with original tier; do not erase historical Drop
  decisions to make counts smaller.
- **ADR062-G3:** Frozen rationale is archived once, with rebased relative links.
  Do not grow a per-change archive, or inventory the generated output recursively.
- Deterministic byte/count reductions do not establish runtime quality or review
  time improvements. Inspect the CSV/map diff rather than rereading archived prose
  on every sync. Roll back navigator, generator, map, CSV and checks together.

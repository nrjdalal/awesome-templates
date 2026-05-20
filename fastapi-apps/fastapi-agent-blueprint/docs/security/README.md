# Security artefacts

Point-in-time reports from the repo's security tooling. These are kept
in git so anyone evaluating the project can see the evidence that
backs up the secret-hygiene claims in [`../../SECURITY.md`](../../SECURITY.md).

## Current contents

| File | What it is | How to regenerate |
|---|---|---|
| `gitleaks-scan-YYYYMMDD.json` | Full git-history gitleaks scan report. Empty array = no findings. | `gitleaks git --report-path docs/security/gitleaks-scan-$(date +%Y%m%d).json --report-format json .` |

## Conventions

- **Reports in this directory must never contain live credentials.** If a
  scan turns up real findings, the report stays **local** until the
  findings are rotated and the tree is scrubbed. Only *clean* reports get
  committed. The value of a committed report is "here is proof the state
  was clean on this date" — that property only holds if we do not commit
  dirty ones.
- **Filenames carry the scan date** (`YYYYMMDD`) so that a reader can
  immediately tell whether the evidence is fresh.
- **One report per tool** is enough. When a newer scan lands, replace
  the older file rather than accumulating — `git log` keeps the history.

## Related

- [`SECURITY.md`](../../SECURITY.md) — vulnerability reporting and the secret-hygiene policy.
- [`.pre-commit-config.yaml`](../../.pre-commit-config.yaml) — where the
  `gitleaks` hook is wired in so every commit is scanned before it lands.

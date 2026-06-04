# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, please email the maintainers directly. We will respond within 48 hours and work with you to understand and address the issue.

## Supported Versions

| Version  | Supported |
|----------|-----------|
| 0.7.x    | Yes       |
| < 0.7.0  | No        |

Pre-1.0: only the latest minor line receives security fixes. Upgrade to the
newest `0.7.x` patch to pick them up.

## Disclosure Policy

When we receive a security bug report, we will:

1. Confirm the problem and determine affected versions
2. Audit code to find any similar problems
3. Prepare fixes and release as quickly as possible

## Secret Hygiene

This is a template repo that visitors clone and adopt wholesale, so a
leaked credential here gets reproduced in every downstream fork. The
hygiene rules below are load-bearing, not aspirational.

### Policy

- **No real credentials in committed files, ever.** Every value in
  [`_env/*.env.example`](_env/) must be a placeholder (safe default,
  dummy host, or the literal `REPLACE_ME`). Real secrets belong in
  `_env/local.env` — gitignored, never staged.
- **Pre-commit guard.** [`gitleaks`](https://github.com/gitleaks/gitleaks)
  runs as a pre-commit hook (see
  [`.pre-commit-config.yaml`](.pre-commit-config.yaml)) and blocks a
  commit that introduces a detected key. Running `make setup` (or
  `pre-commit install`) wires it in.
- **Clean-tree evidence is archived.** Full-history `gitleaks git`
  scans are committed under [`docs/security/`](docs/security/) so
  anyone evaluating the project can verify the state themselves.

### If you suspect a leak in this repo

1. **Do not open a public issue.** Email the maintainers as described above.
2. Include the file path and line, not the raw key (they already know what it is).
3. Credential rotation happens first; the public discussion happens
   only after the key is invalidated upstream.

### If gitleaks flags your commit

1. Do not push.
2. If the finding is real — remove the value, rewrite the commit, and
   rotate the credential upstream even if the commit never reached a
   remote.
3. If the finding is a false positive — confirm with a maintainer
   before adding it to a gitleaks allowlist. Prefer fixing the string
   (e.g. obviously-dummy prefix) over loosening the scanner.

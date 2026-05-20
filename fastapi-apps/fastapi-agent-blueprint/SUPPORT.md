# Support

## Scope of support

**In scope:**
- Bug reports on shipped features (use [GitHub Issues](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues))
- Security vulnerabilities (email the maintainer — see [SECURITY.md](SECURITY.md))
- Documentation drift (factual errors, broken links, stale examples)
- Good-first-issue PR review (see [CONTRIBUTING.md](CONTRIBUTING.md))

**Out of scope:**
- Deployment and infrastructure consulting
- Custom feature development on request
- Debugging your application's business logic
- OS/Python combinations not listed in the [compatibility matrix](docs/compatibility.md)

## Response SLA

| Type | Target |
|---|---|
| Security issues | 48 hours |
| Bug triage | 7 days |
| Feature requests | Best effort (no guarantee) |

This project is maintained by **one person**. Response times are best-effort outside the SLA. If you need faster support for a production deployment, consider commercial FastAPI support options.

## Breaking-change policy

This project follows [Semantic Versioning](https://semver.org/):

- **MAJOR** (`x.0.0`) — breaking changes to the public API, domain structure, or CLI contract. A migration guide is included in the release notes.
- **MINOR** (`0.x.0`) — new features. Existing domains must not break.
- **PATCH** (`0.0.x`) — bug fixes and documentation updates.

During the `0.x` series, MINOR bumps may introduce breaking changes with a documented migration path. This follows the same convention as FastAPI and Pydantic.

## What will not be supported

- **Non-semver dependencies pinning** — the blueprint uses `>=` bounds; exact pins are your project's responsibility.
- **Windows native** (non-WSL2) — the harness hooks use POSIX shell; Windows users should use WSL2. Contributions welcome.
- **Downgrading** — the project does not ship downgrade migrations. Pin to a release tag if you need stability.

## Asking questions

Prefer [GitHub Discussions](https://github.com/Mr-DooSun/fastapi-agent-blueprint/discussions) for usage questions — it keeps answers searchable for future users. Reserve GitHub Issues for confirmed bugs and feature proposals with a clear use case.

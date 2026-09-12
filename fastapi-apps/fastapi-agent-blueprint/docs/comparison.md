# Choosing a backend foundation and collaboration workflow

Use this guide to decide whether the blueprint fits your project. Evaluate the
backend architecture and the repository-specific AI harness together: adopting
both means learning the code structure and the process used to change it.

<a id="how-it-compares"></a>
<a id="feature-matrix"></a>

## What you gain, and what you take on

| Need | What this blueprint offers | Adoption cost or boundary |
|---|---|---|
| Multiple business domains | Shared CRUD bases, domain discovery, and a consistent Router → Service → Repository path. | Learn the layer boundaries, DTO conventions, and dependency-injector wiring; a small API may not justify the structure. |
| API, worker, and admin access to business logic | FastAPI, Taskiq, and NiceGUI surfaces around domain services. | Learn each interface's contracts and authentication requirements. The MCP server is still planned. |
| A local evaluation before provisioning services | SQLite, InMemory infrastructure, and deterministic AI stubs. | Evaluation does not validate production capacity or model quality. Real deployments need infrastructure, credentials, and operational configuration. |
| AI features without making them mandatory | Optional embedding, LLM, and RAG adapters and examples. | Select and configure provider extras, models, credentials, and storage appropriate to your service. |
| Several contributors using AI coding tools | Shared rules and skills, a plan/execute workflow, checks, and review procedures across tool adapters. | Contributors must set up their tools and retain human review. Some workflow controls are reminders, not blocking checks. |
| Continued architectural consistency | Import checks, documented contracts, review checklists, and guideline synchronization. | These controls require maintenance as your application changes; they do not prove every implementation is correct. |

Start with the [backend demo](../README.md#quickstart) and the
[API-change workflow](../README.md#ai-collaboration-harness). Try one domain
change before deciding whether the conventions fit your team.

<a id="when-not-to-use-this-blueprint"></a>

## When a different starting point may fit better

- **A small, single-purpose API:** a minimal FastAPI application can avoid
  abstractions you do not yet need.
- **A customer frontend included from day one:** inspect a full-stack starter
  against your frontend, authentication, and deployment requirements. This
  blueprint's admin UI serves operators, not your customer application.
- **An established architecture you want to retain:** assess individual patterns
  before copying shared infrastructure or adopting the full harness.
- **A framework or raw-throughput decision:** benchmark your own workload and
  compare deployment and ecosystem requirements. This repository is not a
  comparative performance study.
- **A standalone, framework-independent harness:** the rules and skills here
  reference this repository's paths, layers, and commands. Extracting them needs
  adaptation; a turnkey independent harness package is not provided.

<a id="why-not-litestar-or-robyn"></a>
<a id="why-not-fastapifull-stack-fastapi-template"></a>
<a id="why-not-cookiecutter-based-templates"></a>

## Alternatives to explore

The links below are starting points, not feature rankings. Check the current
documentation and code of each candidate for the capabilities you need.

| Decision | Official sources to inspect |
|---|---|
| Build a small FastAPI application yourself | [FastAPI tutorial](https://fastapi.tiangolo.com/tutorial/) |
| Evaluate another template's structure and setup | [Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template), [s3rius/FastAPI-template](https://github.com/s3rius/FastAPI-template), [teamhide/fastapi-boilerplate](https://github.com/teamhide/fastapi-boilerplate) |
| Compare Python web frameworks | [Litestar](https://docs.litestar.dev/), [Robyn](https://robyn.tech/) |
| Generate a project from a configurable template | [Cookiecutter](https://cookiecutter.readthedocs.io/) |

For every candidate, check: can the team understand one feature end-to-end,
run it locally, verify changes, configure deployment, and maintain its chosen
conventions? Feature counts alone do not answer those questions.

## Adoption paths

- **New project:** use the GitHub template, run the evaluation, then follow the
  [first-domain tutorial](tutorial/first-domain.md).
- **Existing project:** use the [adoption guide](adoption.md) to assess a gradual
  introduction of patterns. Copying `_core` or the harness requires checking
  dependencies and compatibility with your application's conventions.
- **Manual or AI-assisted development:** both use the same backend structure.
  The [tool guide](ai-development.md) adds AI collaboration to that foundation;
  the [shared operating model](ai/shared/target-operating-model.md) explains
  workflow responsibilities and exceptions.

Treat future upstream changes as code to review against your own modifications,
not as automatically safe template upgrades.

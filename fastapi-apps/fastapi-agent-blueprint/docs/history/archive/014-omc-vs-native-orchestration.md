# 014. OMC vs Native Orchestration Decision

- Status: Accepted
- Date: 2026-03-24 ~ 2026-04-05
- Related Documents: None

## Summary

To fill the absent orchestration layer (multi-agent coordination, autonomous execution), we chose Claude Code's native Plugin system over OMC — evaluating built-in capabilities before adopting an external dependency.

## Background

- **Trigger**: The project had 11 domain skills + Serena + hooks, but no orchestration layer — limitations were anticipated for simultaneous multi-domain refactoring and complex task decomposition.
- **Decision type**: Upfront design — deliberated across three sessions before the need became acute.

The project has 11 domain skills + Serena + settings.json hooks established,
but an **orchestration layer** (multi-agent coordination, autonomous execution, model routing) is absent.

There are two options to fill this gap:
1. **OMC (Oh My ClaudeCode)** adoption -- a third-party orchestration wrapper
2. **Native** -- Claude Code's built-in Plugin system + `/team` utilization

## Problem

The project is currently operational without an orchestration layer, but limitations are anticipated in these scenarios:
- Simultaneous refactoring across 3+ domains
- Automatic decomposition and parallel execution of complex tasks
- Need for a standard interface when porting to production projects

## Alternatives Considered

### A. Thin OMC Adoption

Delegate only orchestration to OMC while keeping existing domain skills.

**Advantages:**
- `/autopilot`, `/team`, `/ultrapilot` immediately available (zero-config)
- 28 predefined agents (executor, debugger, designer, etc.)
- Automatic model tier routing (Haiku/Sonnet/Opus)
- Multi-provider (`omc ask codex/gemini`)
- Community standard interface -> reduced learning curve when moving between projects

**Disadvantages:**
- External npm dependency (`npm install -g oh-my-claudecode`)
- Risk of OMC's autonomous agents violating architecture absolute-prohibition rules
- Context window overhead from 28 agent definitions
- Dependency on OMC maintainer (compatibility risk with Claude Code updates)
- Risk of skill accumulation + keyword conflicts from Learner (auto skill suggestion)

### B. Native Plugin System + /team (chosen)

Build commands/agents/hooks using Claude Code's official Plugin system.

**Advantages:**
- Anthropic official -- long-term stability guaranteed
- No external dependencies (directory drop-in)
- Existing 11 skills are fully compatible
- Minimal context overhead (define only what's needed)
- `/team` command is already built-in (multi-agent coordination)

**Disadvantages:**
- autopilot, model tiering, etc. must be implemented manually
- Not a community standard -> structure may vary between projects
- Higher initial setup cost than OMC

### C. Full OMC Adoption

Migrate existing skills to OMC format and fully adopt the Conductor model.

**Disadvantages outweigh Option A, so this was eliminated early:**
- Migration cost for existing 11 skills
- Complete dependency on OMC
- Full adoption is risky when team OMC proficiency is at zero

## First Discussion (cross-session-briefing session)

**Conclusion: Option B selected**

Premises at the time:
- 11 skills + Serena + hooks already cover OMC features more precisely
- Team OMC proficiency is 0, conservative team culture
- No tasks currently require multi-agent coordination

Learning curve analysis:

| What needs to be learned | Weight | Does OMC solve it? |
|---|---|---|
| DDD 4-layer rules, absolute prohibitions | 30% | No |
| Conversion patterns (model_validate, model_dump) | 15% | No |
| Domain-specific knowledge | 25% | No |
| Skill contents (what each skill does) | 20% | No |
| How to invoke skills | 5% | Yes |
| Orchestration usage | 5% | Yes |

OMC only reduces ~10% of the learning curve, and the core 90% is addressed by the `/onboarding` skill.

Agreed escalation path:
```
Single agent -> Agent Teams -> (if needed) OMC
```

## Second Discussion (2026-03-24, this session)

### Background for Re-evaluation

Premises from the first discussion changed:
- hooks are **still not configured**, Agent Teams are also **not configured**
- The orchestration layer is effectively **empty**
- A cost comparison between building it directly vs. layering OMC on top is needed

### context7 Investigation Results (new findings)

**Claude Code Native Plugin System Confirmed:**

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json          # Metadata
├── commands/                 # Slash commands (*.md)
├── agents/                   # Specialized agents (*.md)
├── skills/                   # Skills (SKILL.md)
├── hooks/                    # Event handlers (hooks.json)
├── .mcp.json                 # MCP tool configuration
└── README.md
```

- Claude Code **already has** a built-in `/team` command (native team agents with built-in coordination)
- The Plugin system has the **same structure** as OMC (commands/agents/skills/hooks)
- OMC documentation directly states: "native '/team' utilizes Claude Code native team agents"

**OMC's actual differentiators (narrowed down):**

| Feature | Claude Code Built-in | OMC Additional |
|---|---|---|
| Multi-agent | `/team` (built-in) | `/omc-teams` (tmux external workers) |
| Skill system | SKILL.md (built-in) | Same format |
| Agent definitions | `agents/*.md` (Plugin) | 28 predefined |
| Autonomous execution | Write custom command | `/autopilot`, `/ultrapilot` immediately available |
| Model routing | Manual specification | Automatic tiering |
| Multi-provider | N/A | `omc ask codex/gemini` |

**Benchmark scores:**
- Claude Code Plugin: 80.85
- OMC: 75.44
- Claude Code Tresor (alternative plugin pack): 78.65

### Key Insights

1. **Domain specialization is handled by Skills** -- whether OMC or native, domain skills must be written directly regardless
2. **OMC's added value is orchestration convenience** -- autopilot, model tiering, 28 agents
3. **Claude Code Plugin is converging in the same direction as OMC** -- with Anthropic official support
4. **Built-in `/team` + Plugin have not been tried yet** -- evaluating built-in capabilities should come before OMC adoption
5. **Skill formats are compatible** -- starting native means low switching cost to OMC later

### Arguments for OMC Adoption (added in second discussion)

- It is true that OMC is more convenient than building built-in capabilities yourself
- If someone familiar with OMC joins the project, orchestration is immediately usable
- Converging toward a community standard -> freedom of movement between projects

### Arguments for Native Selection (organized in second discussion)

- "Adopting an external tool without even trying the built-in features is a decision made without evaluation"
- Anthropic's official Plugin system is converging in the same direction -> more stable long-term
- OMC can always be added later, but removing it after adoption is difficult
- Context window savings (28 agent definitions not loaded)

## Third Discussion (2026-04-05)

### Background for Re-evaluation

- Blueprint project is about to enter actual development phase
- Current state: 97 files, ~2,200 lines, 1 business domain (user), 15 skills, 2 hooks
- Target state: 10+ domains, 5+ team members (enterprise-grade AI Agent Backend Platform)
- Needed to evaluate whether OMC adoption should happen before or after scaling

### OMC Conflict Analysis (detailed investigation)

| Area | Risk | Detail |
|---|---|---|
| Skills namespace | Low | OMC uses `oh-my-claudecode:<name>` prefix. No collision with existing 15 skills |
| CLAUDE.md | Manageable | OMC uses marker-based injection (`<!-- OMC:START -->...<!-- OMC:END -->`) or preserve mode (`CLAUDE-omc.md`) |
| Hooks | Moderate | OMC registers ~20 hook scripts across 11 lifecycle events. Stacks with existing hooks, doesn't replace. But adds latency and potential noise |
| Context overhead | **High** | 29 agent definitions + 32 skill metadata + hook instructions added to context. Combined with existing CLAUDE.md + project-dna.md + Serena/context7 instructions, significantly reduces available context for actual work |

### Native Orchestration Feasibility Assessment

"Can we build OMC-equivalent orchestration natively?" → **Full equivalence is unrealistic, but unnecessary.**

Feature-by-feature analysis:

| Feature | Build yourself? | Verdict |
|---|---|---|
| tmux parallel workers | **Skip** — `/team` built-in already handles Claude-to-Claude parallelism. OMC's tmux is for multi-provider (Codex/Gemini), not needed now |
| autopilot (autonomous execution) | **Feasible, 1-2 days with AI assistance** — SKILL.md that chains Plan→Agent(parallel)→review-architecture. Domain-aware autopilot > OMC's generic autopilot |
| Model routing (Haiku/Sonnet/Opus) | **Already available** — Agent tool has `model` parameter. Define agents/*.md with model frontmatter. No custom logic needed |
| Multi-provider (Codex/Gemini) | **Not possible natively** — OMC-exclusive feature. Not needed currently |

Key insight: AI-assisted development dramatically lowers build cost for custom tooling.
The remaining challenge is not building but **design iteration and maintenance when Claude Code updates**.
However, SKILL.md and agents/*.md are markdown files — low breakage risk and easy to fix,
unlike OMC's npm package + 20 hook scripts.

### Industry Trend Context (2026-04)

- CLAUDE.md, `.cursorrules`, `AGENTS.md` are becoming standard project-level AI configuration files
- Gartner predicts 40% of enterprise apps will integrate task-specific AI agents by 2026
- The practice of configuring AI agents for projects = **DX (Developer Experience) Engineering** or **dev-environment provisioning**
- Current project's 15 skills + security hooks + project-dna.md = **Platform Engineering level** customization

Realistic distribution of who does this:

| Depth | Who | Analogy |
|---|---|---|
| CLAUDE.md with a few rules | Most developers | `.gitignore` |
| Install frameworks/plugins (OMC etc.) | Team leads | Using GitHub Actions templates |
| **Custom skills + hooks design** | **Senior/Lead (few)** | **Designing internal CI/CD pipelines** |
| Full orchestration platform | DX/Platform team | Internal Developer Platform (IDP) |

**The meta is not "every position configures their own AI environment" but rather
"each position works on top of an AI environment configured by the lead."**
This is exactly what the blueprint project is building.

### Reinforced Arguments for Native (Option B)

From first/second discussions, still valid:
- Benchmark: Native Plugin (80.85) > OMC (75.44) — context overhead likely the cause
- OMC's learning curve contribution: ~10% (core 90% is domain knowledge)
- "Adopting without trying built-in features first is an unevaluated decision"
- OMC can be added later; removing after adoption is difficult

New from third discussion:
- `/team` already covers the primary multi-agent use case (Claude-to-Claude parallelism)
- Model routing is trivially achievable via native agent definitions
- Domain-aware autopilot (custom SKILL.md) can outperform OMC's generic autopilot for this project
- Building custom orchestration with AI assistance is feasible in 1-2 days, not weeks
- Markdown-based skills/agents have lower maintenance burden than OMC's npm dependency

## Decision

**Option B selected — Native Plugin system**

The escalation path is confirmed with concrete actions:
```
Phase 1 (now): Single agent + 15 domain skills
  → Action: Use /team and agents/*.md (model routing) in actual development tasks
  → Estimated effort: 1 day for agent definitions

Phase 2 (3+ domains): Add native autopilot
  → Action: Build domain-aware /autopilot skill (Plan→Execute→Verify pipeline)
  → Estimated effort: 1-2 days with AI assistance

Phase 3 (only if needed): Thin OMC adoption
  → Trigger: Confirmed limitations of /team + native autopilot during 3+ domain simultaneous work
  → Trigger: Team member familiar with OMC joins and makes a case for it
  → Trigger: Multi-provider (Codex/Gemini) becomes a real requirement
```

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?

## Future Considerations

1. When entering Phase 1: document experience with `/team` + native agents in actual work
2. When entering Phase 2: build `/autopilot` skill, iterate on design with real tasks
3. Accumulate "specific cases where built-in features fell short" — this becomes the OMC adoption evidence
4. Monitor Claude Code Plugin ecosystem maturity (Anthropic official marketplace, community plugins)
5. If OMC benchmark improves above native or context overhead is resolved, re-evaluate

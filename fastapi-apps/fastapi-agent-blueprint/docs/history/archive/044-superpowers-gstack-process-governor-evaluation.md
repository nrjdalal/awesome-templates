# Harness Evaluation Memo - Superpowers, gstack, and Process Governor

**Status:** Archived evaluation memo (not a final decision)  
**Date:** 2026-04-23  
**Related issue:** [#114](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/114)  
**Branch:** `docs/114-superpowers-gstack-process-governor-eval`

---

## Summary

This archived memo preserves a user-driven evaluation of whether the project should adopt `superpowers`, `gstack`, or a smaller subset of their ideas while continuing to use the existing local harness. The immediate goal was not to finalize a tool choice that day. The goal was to preserve the full reasoning trail so that Claude and Codex could continue the discussion later without losing context.

The investigation started as a product identification task: "what are gstack and superpowers, and are they worth considering before designing more harness logic by hand?" That quickly expanded into a broader harness question. The comparison exposed a structural gap in the current project setup: the repository already has strong project rules, safety controls, and domain-specific skills, but it does not strongly enforce a default process flow such as `brainstorm -> plan -> TDD/verification -> review`.

The user found `superpowers` attractive primarily because of that enforced operating model. The attraction was not "more skills" in the abstract. It was the promise of lower error rates, better problem framing, stronger test and review discipline, and less drift toward local fixes that miss the real problem. The assistant's position during the discussion was that this diagnosis is mostly correct, but that the project likely needs a `process governor` layer more than it needs a full external plugin replacement.

The current working position at the end of the discussion is:

1. `superpowers` has a philosophy that aligns well with the user's quality goals.
2. `gstack` is more compelling as a capability layer than as a full workflow replacement.
3. The repository's local harness is already substantial and should not be treated as "missing" or disposable.
4. The real weakness is weak default routing into the existing good process assets.
5. The leading candidate direction is to keep the local constitution and local domain skills, while adding stronger default process enforcement inspired by `superpowers`.

---

## Background

The project already maintains a non-trivial AI collaboration harness:

- `AGENTS.md` defines the shared project constitution.
- `CLAUDE.md` and `.codex/config.toml` carry tool-specific harness guidance.
- `.agents/skills/` and `.claude/skills/` provide project-local procedures.
- `.codex/hooks/` and `.claude/hooks/` enforce safety, formatting, and drift reminders.
- `docs/ai/shared/` contains shared process references and checklists.

This means the repository is not starting from a blank slate. It already behaves more like a project-specific AI operating environment than a simple prompt file.

There is also relevant prior context. The project previously evaluated OMC and recorded the result in [014-omc-vs-native-orchestration](014-omc-vs-native-orchestration.md). That decision concluded that:

- the project should prefer native harness and plugin capabilities first
- external orchestration convenience alone was not enough to justify immediate adoption
- domain-specific skills and project-specific rules remained the real source of value

The present discussion revisits the broader question from a different angle. Instead of asking "which orchestration wrapper is more convenient?", the user asked whether the project should use more mature external harness components when they demonstrably offer a more reliable operating model than the current local setup.

---

## What Was Investigated

### 1. `gstack`

`gstack` was investigated through Context7, the public repository, and architecture documentation. The tool appears to be:

- a large opinionated workflow and capability pack
- centered around role-based slash skills
- strongly focused on browser automation, QA, release automation, and execution workflows
- backed by a persistent local browser daemon and associated security model

The assistant's working characterization during the discussion was:

- `gstack` is best understood as an execution-capability layer with a strong workflow opinion
- it is not merely a set of prompts
- it brings substantial runtime surface area and operational complexity

### 2. `superpowers`

`superpowers` was investigated through Context7, the public repository, release notes, and the author's public write-up. The tool appears to be:

- a methodology-first skill framework
- strongly centered on enforced process discipline
- especially focused on `brainstorming`, planning, worktrees, TDD, subagent execution, and review
- designed to shape default agent behavior from session start

The assistant's working characterization during the discussion was:

- `superpowers` is best understood as a process and discipline engine
- its most important value is not the existence of skills, but that the skills are treated as mandatory workflow defaults
- its appeal for this project is mostly about error-rate reduction and forcing better problem framing before coding starts

### 3. Current repository harness structure

The assistant inspected the current repository structure and found:

- local planning and bug-fix skills already exist
- local safety hooks are already in place
- destructive actions are already constrained
- formatting and drift reminders already exist
- the repository therefore already has many of the building blocks that a quality-focused harness needs

However, the inspection also showed that the current hooks and rules mainly enforce:

- safety boundaries
- destructive-command prevention
- formatting
- drift reminders

They do not strongly enforce a default problem-solving route such as:

- clarify or reframe before implementation
- write or confirm a plan before coding
- prefer test-first or at least verification-first execution
- require review before considering work complete

That was the main structural gap revealed by the comparison.

---

## Findings

### Finding 1: `gstack` and `superpowers` solve different problems

The comparison clarified that the two tools are not interchangeable:

- `gstack` is execution and capability heavy
- `superpowers` is process and discipline heavy

Treating them as one category of "plugin" would hide the actual choice being made.

### Finding 2: External plugins reduce commodity maintenance, not project-specific maintenance

The user asked whether adopting a stronger external plugin would make sense if it is more robust than the local harness. The assistant's answer was "partly yes, partly no."

The important distinction is:

- external plugins can reduce maintenance of commodity harness layers
- external plugins do not remove the need to maintain project-specific constitution, architecture rules, and domain workflows

In this repository, the project-specific layer remains large and important.

### Finding 3: The project is not lacking process assets; it is lacking strong default routing

The comparison did not reveal "no process exists." Instead, it revealed:

- the project already has good local process skills
- the project already has strong safety controls
- the project already has governance and drift management
- but default routing into those processes is weak

This distinction matters because it changes the likely solution:

- not "replace everything"
- but "strengthen process enforcement"

### Finding 4: The user's interest in `superpowers` is fundamentally about error-rate reduction

The user repeatedly emphasized that:

- the current behavior can miss parts of the context
- agents can focus on immediate fixes rather than root problems
- small changes can later expand into large bug ranges
- `superpowers` feels attractive because it appears to reduce those failure modes

The assistant treated this as a valid and important signal. The real attraction is not novelty. It is operational quality.

### Finding 5: "High-risk only" enforcement is weaker than it sounds

One branch of the discussion asked whether a strict process should be enforced only for high-risk work. The user correctly challenged that framing:

- high risk is often subjective
- many "small" changes later prove to be high risk
- a risk-gating system itself requires classification effort and can be wrong

The assistant agreed and revised the recommendation:

- `default mandatory flow + explicit exceptions only` is more robust than `apply only to high-risk work`

### Finding 6: Skills and constitution alone are not enough

By the end of the discussion, the assistant made a stricter distinction:

- good skills are necessary
- a strong constitution is necessary
- but those two alone do not create reliable default process behavior

The missing piece is a routing or enforcement layer. That layer was summarized during the discussion as a `process governor`.

---

## Chronological Discussion Record

### Phase 1 - Identify the tools

The user first asked for a careful identification of `gstack` and `superpowers`, with explicit permission to take time and ask follow-up questions if needed. The user also noted earlier consideration of OMC.

The assistant:

- searched the local repository for existing references to `gstack`, `superpowers`, and `omc`
- found the archived OMC decision record
- used Context7 and public repository documentation to identify the nature of both tools
- confirmed that both are closer to AI operating systems than to simple utilities

Initial conclusions from that phase:

- `gstack` behaves like a workflow and execution factory with heavy browser and QA capabilities
- `superpowers` behaves like a methodology and discipline engine

### Phase 2 - Compare external plugin adoption to direct harness design

The user then explained the deeper motivation:

- they had originally intended to design the harness directly
- they had not known about OMC, `gstack`, or `superpowers` at first
- now that mature plugins exist, they were open to using them if that would reduce harness maintenance or increase robustness

The user also raised a fair challenge:

- if external plugins are more robust, why not use them?
- and if they are adopted, does customization not still remain necessary anyway?

The assistant responded by distinguishing:

- commodity maintenance handled by plugins
- project-specific maintenance that remains local

The assistant also emphasized that the current repository already has a substantial local harness and should not be treated as empty.

### Phase 3 - Explore replacement, partial adoption, and coexistence

The user then asked a critical structural question:

- should this be partial adoption?
- full replacement?
- or are these systems meant to coexist?

The assistant's answer was:

- coexistence is possible
- but possible coexistence is not always good coexistence
- `superpowers` is more constitution-like and therefore more collision-prone
- `gstack` is more suitable for selective capability adoption

At that point, the assistant's working recommendation was:

- avoid full replacement
- avoid mandatory whole-project `superpowers` adoption for now
- prefer either selective `gstack` capability use or selective adoption of process ideas

### Phase 4 - The key attraction: `brainstorm -> plan -> TDD -> review`

The user then clarified the strongest source of attraction:

- the local agents may already be good
- but `superpowers` has an especially compelling `brainstorm -> plan -> TDD -> review` flow
- the user values that because context can be partially missed and the work can drift away from the real problem
- they believe this kind of workflow lowers error rates and surfaces missed concerns

This changed the center of the conversation.

The assistant then inspected local planning and bug-fix skills and concluded:

- the current harness already has strong individual procedures
- what it lacks is strong default routing into those procedures

This became the turning point in the discussion.

### Phase 5 - Shift from "plugin choice" to "process governor"

Once the user clarified that error-rate reduction and stronger default quality discipline were the real goals, the assistant restated the problem:

- the project likely does not need "more skills" as much as it needs stronger default routing
- the missing layer is not domain logic, but runtime process enforcement

The assistant then introduced the term `process governor` to describe that missing layer:

- something that routes coding requests into the right process by default
- something that makes direct implementation harder without planning
- something that prevents work from being declared complete without verification and review

### Phase 6 - Reject "high-risk only" as the main model

The discussion then examined whether stronger process enforcement should apply only to high-risk work.

The user objected that:

- risk is relative
- many changes look small until they are not
- deciding what counts as high risk becomes its own unreliable classification task

The assistant agreed and revised the recommendation. The better framing is:

- process should be mandatory by default for most coding work
- only narrow, explicit exceptions should bypass it

This was an important refinement.

### Phase 7 - Can the local constitution and local skills simply be updated?

The user then asked whether the answer might be straightforward:

- if `superpowers` philosophy fits the quality goal
- and the structural weakness is weak routing
- then why not simply update the local constitution and local skills?

The assistant answered:

- this is mostly correct
- but not complete

The key correction was:

- updating skills and constitution is necessary
- but not sufficient

The project also needs a stronger runtime routing layer. Without that, good skills remain optional in practice.

### Phase 8 - Final working position for the day

By the end of the conversation, the working position was:

- the user's attraction to `superpowers` is justified
- the attraction is fundamentally about quality and lower error rates
- the current repository already has many strong local assets
- the main problem is weak default routing into those assets
- the likely answer is not immediate full plugin replacement
- the likely answer is a stronger local `process governor`, potentially informed by `superpowers`, while keeping the local constitution and domain skills

That working position is still provisional and is intentionally left open for follow-up review.

---

## Current Position

The current provisional position is:

1. The user's quality goals are legitimate and well aligned with the strongest parts of `superpowers`.
2. The current repository should not assume that "good skills exist" means "good process is enforced."
3. `superpowers` remains a real adoption candidate, but the most likely value lies in its operating philosophy rather than in immediate full takeover.
4. `gstack` remains interesting as a partial capability layer, especially where runtime QA or execution support becomes useful.
5. The most promising direction today is to preserve the local constitution and local domain-specific skills, while strengthening default routing through a local `process governor`.

This is not a final decision. It is the best current synthesis of the conversation.

---

## Open Questions For Tomorrow

1. Is full `superpowers` adoption more valuable than strengthening the local harness with `superpowers`-style defaults?
2. Should `gstack` be treated only as a capability layer candidate, or does it deserve deeper workflow consideration?
3. Should `TDD` be enforced literally, or should the harness generalize the requirement to a broader `verification-first` rule for cases where strict TDD is impractical?
4. What should count as an explicit exception to the default flow?
5. Which layer should own the `process governor` logic:
   - constitution text
   - local skill wrappers
   - session-start guidance
   - prompt-submit routing hooks
   - stop-time enforcement reminders
6. How should the final model stay consistent across both Claude and Codex without duplicating too much harness logic?

---

## Appendix A - Detailed Dialogue Digest

### A1. User's original concern

The user did not start from plugin hype. The user started from practical harness design and only later learned that `OMC`, `superpowers`, and `gstack` already existed. That created a fair strategic question: if stronger external harnesses already exist, perhaps the project should use them instead of hand-building everything.

### A2. Earlier OMC context matters

The user explicitly connected this conversation to earlier OMC evaluation. This mattered because it showed a stable concern across multiple discussions: not just "which tool is coolest?", but "what belongs in local harness code versus external tooling?"

### A3. The user's strongest concern is not convenience

A key point repeated throughout the conversation is that the user is not primarily chasing convenience. The core concern is lower error rates and higher reliability in AI-assisted work. That is why `superpowers` felt compelling.

### A4. The user challenged weak framings directly

The user pushed back on:

- the idea that "high risk only" is an easy filter
- the assumption that plugin adoption must mean full replacement
- the assumption that seeing the current weakness only through comparison somehow makes it less real

Those objections improved the quality of the discussion and materially changed the assistant's recommendations.

### A5. Assistant corrections during the discussion

Several refinements were made along the way:

- the issue is not the absence of process assets
- the issue is weak default routing into existing process assets
- the likely missing layer is process enforcement
- `skills + constitution` is not enough without routing and enforcement
- the best target may be `superpowers` philosophy rather than `superpowers` as a full product

### A6. The final mental model

The cleanest abstraction reached during the discussion was:

- local constitution owns project truth
- local domain skills own project-specific procedures
- external plugins may own commodity capability layers
- a process governor is needed to reliably route work through the right process by default

That model should be tested tomorrow rather than assumed.

---

## Appendix B - Candidate Next Steps

### B1. Discussion checklist

Use the following checklist tomorrow:

- restate the user goal in one sentence: lower error rates through stronger process defaults
- decide whether the team is evaluating a product or a philosophy
- decide whether strict TDD is the right universal term for this project
- define the minimum viable scope of a process governor
- decide whether `gstack` deserves a focused capability trial
- decide whether `superpowers` deserves a direct pilot or only pattern extraction

### B2. Candidate experiment directions

#### Option A - Native process governor

Keep the local constitution and local skills. Add stronger default routing and enforcement:

- default coding flow requires planning first
- implementation requires verification before completion
- review is required before closure
- exceptions are narrow and explicit

#### Option B - Thin `superpowers` pilot

Try a constrained pilot to understand actual fit:

- no full project replacement yet
- use it to observe workflow quality and friction
- measure whether it improves framing and verification in practice

#### Option C - Capability-only `gstack` pilot

Try `gstack` only where its strengths are clearest:

- browser-heavy QA
- runtime validation
- selected release or review support

#### Option D - Hybrid evaluation

Treat:

- `superpowers` as a philosophy candidate
- `gstack` as a capability candidate
- local harness as the long-term owner of project-specific truth

### B3. Small PoC scope ideas

If a small proof of concept is wanted, candidate scopes include:

1. one feature-planning workflow
2. one real bug-fix workflow
3. one medium-sized refactor request

Each should be evaluated against:

- framing quality
- context retention
- verification rigor
- review discipline
- user burden
- cross-tool consistency

# 018. Domain Event Infrastructure Removal

- Status: Accepted
- Date: 2026-04-02
- Related ADR: [001](001-celery-to-taskiq.md)(Taskiq), [007](../007-di-container-and-app-separation.md)(App Separation), [011](../011-3tier-hybrid-architecture.md)(3-Tier Hybrid)

## Summary

We deliberately removed the Domain Event infrastructure (event bus, per-domain event classes) because, in our monolithic modular architecture, Service direct calls and Taskiq workers already cover all inter-domain communication needs — Domain Events added complexity without consumers.

## Background

- **Trigger**: During a documentation cleanup, we noticed that `DomainEvent`, `UserCreated`, `UserUpdated`, and `UserDeleted` classes existed but had zero consumers. No code dispatched or subscribed to these events. They were pure definitions with no runtime behavior.
- **Decision type**: Experience-based correction — the event infrastructure was built proactively following DDD literature, but practical usage never materialized.

The project had implemented a standard DDD event pattern:

```python
# _core/domain/events/domain_event.py (deleted)
class DomainEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    occurred_at: datetime = Field(default_factory=datetime.now)
    event_type: str

# user/domain/events/user_events.py (deleted)
class UserCreated(DomainEvent):
    event_type: str = "user.created"
    user_id: int
    username: str
```

## Problem

### 1. Zero Consumers

No event bus, no subscribers, no dispatch calls existed. The event classes were type definitions with no runtime effect — pure dead code.

### 2. Existing Mechanisms Already Cover the Use Cases

- **Synchronous cross-domain calls**: Service-to-Service via DI container (Protocol-based). When domain A needs data from domain B, it calls B's service directly.
- **Asynchronous side effects**: Taskiq workers handle fire-and-forget operations. When a user action triggers a background job, the router or service calls `task.kiq()` directly.

Domain Events would be a third mechanism doing what these two already do, adding indirection without benefit.

### 3. Premature Abstraction for Current Scale

With 1 active domain (user) and a target of 10+ domains, introducing an event bus now would mean:
- Building event dispatch/subscribe infrastructure for a single domain
- Every new domain would need to decide: Service call, Taskiq task, or Domain Event?
- Three communication patterns where two suffice increases cognitive load for the team

## Alternatives Considered

### A. Build a Full Event Bus

Implement an in-process event bus (mediator pattern) with publish/subscribe support.

Rejected: The project's cross-domain communication patterns (Protocol-based DIP for reads, Taskiq for async) already provide clear, debuggable communication channels. An event bus adds indirection that makes control flow harder to trace — a significant cost when the team is small and growing.

### B. Keep Event Definitions for Future Use

Leave the event classes in place as a "ready-to-use" infrastructure for when domains need pub/sub.

Rejected: Dead code that "might be useful someday" has a real cost: new team members must understand it, documentation must explain it, and it creates a false impression that events are part of the architecture. If event-driven communication becomes necessary in the future, it should be designed for the actual use case, not retrofitted from skeleton classes.

### C. Use Events Only for Audit/Logging

Keep events as a logging mechanism for tracking domain actions.

Rejected: The project uses structured logging and database audit trails for this purpose. Domain Events for logging would be an over-engineered solution to a problem already solved by simpler means.

## Decision

Remove all Domain Event infrastructure:
- Delete `src/_core/domain/events/domain_event.py`
- Delete `src/user/domain/events/` directory
- Remove event references from 9 documentation and configuration files

The project's inter-domain communication strategy is:

| Communication Type | Mechanism | Example |
|-------------------|-----------|---------|
| Synchronous read | Protocol-based Service call via DI | Domain A reads Domain B's data |
| Synchronous write | Service direct call | Domain A triggers Domain B's operation |
| Asynchronous | Taskiq worker task | Background processing after user action |

If event-driven architecture becomes necessary (e.g., many-to-many domain reactions, event sourcing), it should be introduced as a new ADR with concrete use cases — not as speculative infrastructure.

## Rationale

| Decision | Reason |
|----------|--------|
| Full removal over keeping skeletons | Dead code has maintenance cost. Future needs will have different requirements than what was pre-built |
| No event bus alternative proposed | Two clear communication channels (DI Service calls + Taskiq) cover sync and async cases. A third channel must justify its existence |
| Documented as ADR | "Why don't we use Domain Events?" is a question that DDD-experienced developers will ask. This record prevents re-introducing the same pattern without new justification |

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?

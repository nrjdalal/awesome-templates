from __future__ import annotations

from typing import Protocol, runtime_checkable

from src._core.domain.value_objects.agent_usage_record import AgentUsageRecord


@runtime_checkable
class AgentUsageRecorderProtocol(Protocol):
    async def record_usage(self, record: AgentUsageRecord) -> AgentUsageRecord: ...

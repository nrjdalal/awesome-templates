from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DailyCount:
    """One day's record count from a date-grouped aggregate.

    A read result that is intrinsically a value and never mutated downstream, so
    it is a frozen VO rather than a DTO — the same reasoning as ``CursorPage``
    and ``VectorSearchResult``. ``@dataclass(frozen=True)`` (not the Pydantic
    ``ValueObject`` base) because there is nothing to validate at runtime.

    Produced by ``BaseRepository.count_datas_by_day``. Days with no rows are
    **absent** rather than zero-filled: the repository reports what the table
    contains, and deciding whether a gap means "zero" or "no data yet" is the
    caller's business (the admin dashboard fills gaps for its chart, an alerting
    consumer might not).
    """

    day: date
    count: int

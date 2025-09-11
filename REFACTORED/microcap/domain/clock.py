from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, date


@dataclass
class Clock:
    as_of: date | None = None

    def now(self) -> datetime:
        if self.as_of is None:
            return datetime.now()
        # Use noon to avoid DST edge cases when normalizing
        return datetime.combine(self.as_of, datetime.min.time()) + timedelta(hours=12)


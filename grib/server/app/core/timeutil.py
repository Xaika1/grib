import re
from datetime import UTC, datetime, timedelta


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


def to_ms(dt: datetime) -> int:
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return int(dt.replace(tzinfo=UTC).timestamp() * 1000)


def from_ms(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, UTC).replace(tzinfo=None)


_RANGE = re.compile(r"^(\d+)\s*([smhdw])$")
_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def parse_range(value: str) -> timedelta:
    m = _RANGE.match((value or "").strip().lower())
    if not m:
        return timedelta(hours=6)
    return timedelta(seconds=int(m.group(1)) * _UNITS[m.group(2)])

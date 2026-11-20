from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any

from app.core.timeutil import to_ms, utcnow

TIME_NAMES = {"time", "ts", "timestamp", "date", "datetime", "created_at", "period", "bucket", "время", "дата"}


@dataclass
class Normalized:
    series: list[dict] = field(default_factory=list)
    table: dict = field(default_factory=dict)
    time_column: str | None = None

    def as_dict(self) -> dict:
        return {"series": self.series, "table": self.table, "time_column": self.time_column}


def to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, date):
        return datetime.combine(value, time())
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        v = float(value)
        if v > 1e11:
            v /= 1000
        try:
            return datetime.fromtimestamp(v, UTC).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        if len(text) < 8 or not text[:4].isdigit():
            return None
        try:
            return to_datetime(datetime.fromisoformat(text))
        except ValueError:
            return None
    return None


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


def _num(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if _is_number(value):
        f = float(value)
        return f if f == f and f not in (float("inf"), float("-inf")) else None
    return None


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if value == value and value not in (float("inf"), float("-inf")) else None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    return str(value)


def normalize(columns: list[str], rows: list[tuple | list]) -> Normalized:
    result = Normalized(table={"columns": list(columns), "rows": [[jsonable(v) for v in r] for r in rows]})
    if not columns:
        return result

    samples: list[Any] = []
    for i in range(len(columns)):
        samples.append(next((r[i] for r in rows if r[i] is not None), None))

    time_idx: int | None = None
    for i, name in enumerate(columns):
        if name.lower() in TIME_NAMES and to_datetime(samples[i]) is not None:
            time_idx = i
            break
    if time_idx is None:
        for i, s in enumerate(samples):
            if isinstance(s, (datetime, date)):
                time_idx = i
                break
    num_idx = [i for i, s in enumerate(samples) if i != time_idx and _is_number(s)]
    label_idx = [i for i in range(len(columns)) if i != time_idx and i not in num_idx]
    if time_idx is not None:
        result.time_column = columns[time_idx]

    now_ms = to_ms(utcnow())
    series: dict[str, list] = {}
    for row in rows:
        if time_idx is not None:
            dt = to_datetime(row[time_idx])
            if dt is None:
                continue
            ts = to_ms(dt)
        else:
            ts = now_ms
        label = " / ".join(str(row[i]) for i in label_idx if row[i] is not None)
        for i in num_idx:
            if label and len(num_idx) == 1:
                name = label
            elif label:
                name = f"{label} · {columns[i]}"
            else:
                name = columns[i]
            series.setdefault(name, []).append([ts, _num(row[i])])

    for name, points in series.items():
        if time_idx is not None:
            points.sort(key=lambda p: p[0])
        result.series.append({"name": name, "points": points})
    return result

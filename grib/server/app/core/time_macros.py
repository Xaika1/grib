import re
from datetime import datetime

_MACRO = re.compile(r"\$\{?(from|to|interval)\}?\b")


def _literal(dt: datetime) -> str:
    return "'" + dt.strftime("%Y-%m-%d %H:%M:%S") + "'"


def suggested_interval(t_from: datetime, t_to: datetime, points: int = 200) -> int:
    return max(1, int((t_to - t_from).total_seconds() // points))


def apply(sql: str, t_from: datetime, t_to: datetime, interval_sec: int | None = None) -> str:
    interval = interval_sec or suggested_interval(t_from, t_to)
    values = {"from": _literal(t_from), "to": _literal(t_to), "interval": str(interval)}
    return _MACRO.sub(lambda m: values[m.group(1)], sql)

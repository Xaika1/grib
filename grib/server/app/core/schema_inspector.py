import threading
import time

from sqlalchemy import MetaData, Table, inspect
from sqlalchemy.exc import NoSuchTableError, SQLAlchemyError
from sqlalchemy.types import Date, DateTime, Numeric, Integer, Float, Time

from app.core.connector import Connector, SourceConfig
from app.core.errors import BadRequest, QueryError

_TTL_SEC = 60


def _kind(sa_type) -> str:
    try:
        if isinstance(sa_type, (DateTime, Date, Time)):
            return "time"
        if isinstance(sa_type, (Integer, Float, Numeric)):
            return "number"
        py = sa_type.python_type
        if py in (int, float):
            return "number"
    except (NotImplementedError, AttributeError):
        pass
    return "text"


class SchemaInspector:
    def __init__(self, connector: Connector) -> None:
        self._connector = connector
        self._cache: dict[str, tuple[float, dict]] = {}
        self._tables: dict[tuple[str, str], tuple[float, Table]] = {}
        self._lock = threading.Lock()

    def schema(self, cfg: SourceConfig, refresh: bool = False) -> dict:
        key = cfg.fingerprint()
        with self._lock:
            hit = self._cache.get(key)
        if hit and not refresh and time.monotonic() - hit[0] < _TTL_SEC:
            return hit[1]
        try:
            insp = inspect(self._connector.engine(cfg))
            tables = []
            for name in sorted(insp.get_table_names() + insp.get_view_names()):
                cols = [
                    {"name": c["name"], "type": str(c["type"]), "kind": _kind(c["type"])}
                    for c in insp.get_columns(name)
                ]
                tables.append({"name": name, "columns": cols})
        except SQLAlchemyError as exc:
            raise QueryError(f"Не удалось прочитать схему: {str(getattr(exc, 'orig', exc))[:300]}") from exc
        data = {"tables": tables}
        with self._lock:
            self._cache[key] = (time.monotonic(), data)
        return data

    def table(self, cfg: SourceConfig, name: str) -> Table:
        key = (cfg.fingerprint(), name)
        with self._lock:
            hit = self._tables.get(key)
        if hit and time.monotonic() - hit[0] < _TTL_SEC:
            return hit[1]
        known = {t["name"] for t in self.schema(cfg)["tables"]}
        if name not in known:
            raise BadRequest(f"Таблица «{name}» не найдена в источнике")
        try:
            table = Table(name, MetaData(), autoload_with=self._connector.engine(cfg))
        except (NoSuchTableError, SQLAlchemyError) as exc:
            raise QueryError(f"Не удалось прочитать таблицу «{name}»") from exc
        with self._lock:
            self._tables[key] = (time.monotonic(), table)
        return table

    def invalidate(self) -> None:
        with self._lock:
            self._cache.clear()
            self._tables.clear()

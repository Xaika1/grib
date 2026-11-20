import hashlib
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.core.errors import BadRequest, QueryError

SOURCE_TYPES = ("postgresql", "mysql", "sqlite")
DEFAULT_PORTS = {"postgresql": 5432, "mysql": 3306}


@dataclass(frozen=True)
class SourceConfig:
    type: str
    host: str = ""
    port: int | None = None
    database: str = ""
    username: str = ""
    password: str = field(default="", repr=False)
    id: int | None = None

    def fingerprint(self) -> str:
        raw = f"{self.type}|{self.host}|{self.port}|{self.database}|{self.username}|{self.password}"
        return hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    truncated: bool
    elapsed_ms: int


def resolve_sqlite_path(database: str) -> Path:
    base = settings.sqlite_dir.resolve()
    path = (base / database).resolve()
    if not path.is_relative_to(base):
        raise BadRequest(f"Файл SQLite должен находиться внутри каталога {base}")
    if not path.is_file():
        raise BadRequest(f"Файл SQLite не найден: {database}")
    return path


def _timeout_ms() -> int:
    return int(settings.query_timeout_sec * 1000)


def _create_engine(cfg: SourceConfig) -> Engine:
    common: dict[str, Any] = {"pool_size": 2, "max_overflow": 2, "pool_pre_ping": True, "pool_recycle": 1800}
    if cfg.type == "postgresql":
        url = URL.create(
            "postgresql+psycopg",
            username=cfg.username or None,
            password=cfg.password or None,
            host=cfg.host or "localhost",
            port=cfg.port or DEFAULT_PORTS["postgresql"],
            database=cfg.database or None,
        )
        options = f"-c default_transaction_read_only=on -c statement_timeout={_timeout_ms()}"
        return create_engine(url, connect_args={"options": options, "connect_timeout": 5}, **common)

    if cfg.type == "mysql":
        url = URL.create(
            "mysql+pymysql",
            username=cfg.username or None,
            password=cfg.password or None,
            host=cfg.host or "localhost",
            port=cfg.port or DEFAULT_PORTS["mysql"],
            database=cfg.database or None,
            query={"charset": "utf8mb4"},
        )
        engine = create_engine(
            url,
            connect_args={"connect_timeout": 5, "read_timeout": int(settings.query_timeout_sec) + 5},
            **common,
        )

        @event.listens_for(engine, "connect")
        def _mysql_readonly(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("SET SESSION TRANSACTION READ ONLY")
            try:
                cur.execute(f"SET SESSION max_execution_time = {_timeout_ms()}")
            except Exception:
                cur.execute(f"SET SESSION max_statement_time = {settings.query_timeout_sec}")
            cur.close()

        return engine

    if cfg.type == "sqlite":
        path = resolve_sqlite_path(cfg.database)
        url = f"sqlite:///file:{path.as_posix()}?mode=ro&uri=true"
        return create_engine(url, connect_args={"check_same_thread": False})

    raise BadRequest(f"Неизвестный тип источника: {cfg.type}")


class Connector:
    def __init__(self) -> None:
        self._engines: dict[str, Engine] = {}
        self._by_source: dict[int, str] = {}
        self._lock = threading.Lock()

    def engine(self, cfg: SourceConfig) -> Engine:
        key = cfg.fingerprint()
        with self._lock:
            engine = self._engines.get(key)
            if engine is None:
                engine = _create_engine(cfg)
                self._engines[key] = engine
            if cfg.id is not None:
                old = self._by_source.get(cfg.id)
                if old and old != key:
                    stale = self._engines.pop(old, None)
                    if stale is not None:
                        stale.dispose()
                self._by_source[cfg.id] = key
            return engine

    def invalidate(self, source_id: int) -> None:
        with self._lock:
            key = self._by_source.pop(source_id, None)
            engine = self._engines.pop(key, None) if key else None
        if engine is not None:
            engine.dispose()

    def dispose_all(self) -> None:
        with self._lock:
            engines = list(self._engines.values())
            self._engines.clear()
            self._by_source.clear()
        for engine in engines:
            engine.dispose()

    def run_query(self, cfg: SourceConfig, sql: str, max_rows: int | None = None) -> QueryResult:
        limit = max_rows or settings.query_max_rows
        started = time.monotonic()
        try:
            engine = self.engine(cfg)
            with engine.connect() as conn:
                raw = conn.connection.dbapi_connection
                if cfg.type == "sqlite":
                    deadline = started + settings.query_timeout_sec
                    raw.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
                cur = raw.cursor()
                try:
                    cur.execute(sql)
                    if cur.description is None:
                        raise QueryError("Запрос не вернул данных")
                    columns = [str(d[0]) for d in cur.description]
                    rows = [tuple(r) for r in cur.fetchmany(limit + 1)]
                finally:
                    cur.close()
                    if cfg.type == "sqlite":
                        raw.set_progress_handler(None, 0)
                conn.rollback()
        except QueryError:
            raise
        except BadRequest:
            raise
        except SQLAlchemyError as exc:
            raise QueryError(_short(exc)) from exc
        except Exception as exc:
            raise QueryError(_short(exc)) from exc
        truncated = len(rows) > limit
        return QueryResult(columns, rows[:limit], truncated, int((time.monotonic() - started) * 1000))

    def test(self, cfg: SourceConfig) -> int:
        result = self.run_query(cfg, "SELECT 1")
        return result.elapsed_ms


def _short(exc: Exception) -> str:
    text = str(getattr(exc, "orig", None) or exc).strip()
    if "interrupted" in text.lower():
        return f"Запрос прерван: превышено время выполнения ({settings.query_timeout_sec:g} с)"
    return text.splitlines()[0][:500] if text else exc.__class__.__name__


connector = Connector()

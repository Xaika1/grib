import asyncio
import logging
import threading
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("grib.event_bus")


@dataclass(eq=False)
class Connection:
    ws: Any
    user_id: int
    alert_projects: set[int] | None
    dashboard_id: int | None = None
    collector_ids: set[int] = field(default_factory=set)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class EventBus:
    def __init__(self) -> None:
        self._conns: set[Connection] = set()
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def add(self, conn: Connection) -> None:
        with self._lock:
            self._conns.add(conn)

    def remove(self, conn: Connection) -> None:
        with self._lock:
            self._conns.discard(conn)

    def subscribe(self, conn: Connection, dashboard_id: int | None, collector_ids: set[int]) -> None:
        with self._lock:
            conn.dashboard_id = dashboard_id
            conn.collector_ids = set(collector_ids)

    def refresh_dashboard(self, dashboard_id: int, collector_ids: set[int]) -> None:
        with self._lock:
            for conn in self._conns:
                if conn.dashboard_id == dashboard_id:
                    conn.collector_ids = set(collector_ids)

    @property
    def connection_count(self) -> int:
        with self._lock:
            return len(self._conns)

    def publish(self, event: dict) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            loop.create_task(self._dispatch(event))
        else:
            asyncio.run_coroutine_threadsafe(self._dispatch(event), loop)

    @staticmethod
    def _match(conn: Connection, event: dict) -> bool:
        kind = event.get("type")
        if kind == "sample":
            return event.get("collector_id") in conn.collector_ids
        if kind == "alert":
            return conn.alert_projects is None or event.get("project_id") in conn.alert_projects
        return False

    async def _dispatch(self, event: dict) -> None:
        with self._lock:
            targets = [c for c in self._conns if self._match(c, event)]
        for conn in targets:
            try:
                async with conn.send_lock:
                    await conn.ws.send_json(event)
            except Exception:
                log.debug("drop websocket of user %s", conn.user_id)
                self.remove(conn)


bus = EventBus()

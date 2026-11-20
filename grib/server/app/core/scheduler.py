import logging
import threading
from datetime import timedelta
from typing import Callable

from sqlalchemy import delete, select

from app.config import settings
from app.core import executor
from app.core.timeutil import utcnow
from app.db import SessionLocal
from app.models import Collector, Sample

log = logging.getLogger("grib.scheduler")


class Scheduler:
    def __init__(self, run_collector: Callable[[int], object], tick_sec: float | None = None) -> None:
        self._run_collector = run_collector
        self._tick_sec = tick_sec or settings.scheduler_tick_sec
        self._stop = threading.Event()
        self._running: set[int] = set()
        self._running_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._last_cleanup = utcnow() - timedelta(days=1)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="grib-scheduler", daemon=True)
        self._thread.start()
        log.info("scheduler started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.wait(self._tick_sec):
            try:
                self.tick()
            except Exception:
                log.exception("scheduler tick failed")

    def tick(self) -> list[int]:
        now = utcnow()
        started: list[int] = []
        with SessionLocal() as session:
            collectors = session.scalars(select(Collector).where(Collector.enabled.is_(True))).all()
            for c in collectors:
                due = c.last_run_at is None or (now - c.last_run_at).total_seconds() >= c.interval_sec
                if not due:
                    continue
                with self._running_lock:
                    if c.id in self._running:
                        continue
                    self._running.add(c.id)
                executor.submit(self._job, c.id)
                started.append(c.id)
        if (now - self._last_cleanup) >= timedelta(hours=1):
            self._last_cleanup = now
            executor.submit(self._cleanup)
        return started

    def _job(self, collector_id: int) -> None:
        try:
            self._run_collector(collector_id)
        except Exception:
            log.exception("collector %s failed", collector_id)
        finally:
            with self._running_lock:
                self._running.discard(collector_id)

    @staticmethod
    def _cleanup() -> None:
        border = utcnow() - timedelta(days=settings.sample_retention_days)
        with SessionLocal() as session:
            session.execute(delete(Sample).where(Sample.ts < border))
            session.commit()

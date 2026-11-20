from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core import query_guard, time_macros
from app.core.connector import connector
from app.core.errors import BadRequest, Conflict
from app.core.event_bus import bus
from app.core.normalizer import normalize
from app.core.permissions import ensure
from app.core.timeutil import to_ms, utcnow
from app.db import SessionLocal
from app.models import AppUser, Collector, Sample
from app.repositories import CollectorRepo, SampleRepo, SourceRepo
from app.schemas.monitoring import CollectorCreate, CollectorUpdate
from app.schemas.query import QueryModel
from app.services import alert_service, source_service


def get_collector(session: Session, user: AppUser, collector_id: int, permission: str = "collector.view") -> Collector:
    col = CollectorRepo(session).get_or_404(collector_id)
    ensure(session, user, col.project_id, permission)
    return col


def list_collectors(session: Session, user: AppUser, project_id: int) -> list[Collector]:
    ensure(session, user, project_id, "collector.view")
    return CollectorRepo(session).for_project(project_id)


def _check_interval(interval: int) -> None:
    if interval < settings.min_collector_interval_sec:
        raise BadRequest(f"Интервал сборщика не может быть меньше {settings.min_collector_interval_sec} с")


def _resolve_query(session: Session, project_id: int, source_id: int, query: str, model) -> tuple[str, dict | None]:
    src = SourceRepo(session).get_or_404(source_id)
    if src.project_id != project_id:
        raise BadRequest("Источник относится к другому проекту")
    if model is not None:
        query = source_service.build_for_source(src, model)
        model_dict = model.model_dump()
    else:
        model_dict = None
    if not query.strip():
        raise BadRequest("Задайте запрос сборщика")
    query_guard.check(time_macros.apply(query, utcnow() - timedelta(minutes=1), utcnow()))
    return query, model_dict


def create_collector(session: Session, user: AppUser, project_id: int, data: CollectorCreate) -> Collector:
    ensure(session, user, project_id, "collector.manage")
    _check_interval(data.interval_sec)
    repo = CollectorRepo(session)
    if repo.by_name(project_id, data.name):
        raise Conflict(f"Сборщик «{data.name}» уже есть в проекте")
    query, model = _resolve_query(session, project_id, data.source_id, data.query, data.query_model)
    col = repo.add(
        Collector(
            project_id=project_id,
            source_id=data.source_id,
            name=data.name,
            query=query,
            query_model=model,
            interval_sec=data.interval_sec,
            enabled=data.enabled,
        )
    )
    session.commit()
    return col


def update_collector(session: Session, user: AppUser, collector_id: int, data: CollectorUpdate) -> Collector:
    col = get_collector(session, user, collector_id, "collector.manage")
    fields = data.model_dump(exclude_unset=True)
    if fields.get("name") and fields["name"] != col.name:
        if CollectorRepo(session).by_name(col.project_id, fields["name"]):
            raise Conflict(f"Сборщик «{fields['name']}» уже есть в проекте")
        col.name = fields["name"]
    if fields.get("interval_sec") is not None:
        _check_interval(fields["interval_sec"])
        col.interval_sec = fields["interval_sec"]
    if fields.get("enabled") is not None:
        col.enabled = fields["enabled"]
    if any(k in fields for k in ("source_id", "query", "query_model", "clear_query_model")):
        source_id = fields.get("source_id") or col.source_id
        model = data.query_model
        if model is None and not data.clear_query_model and "query" not in fields and col.query_model:
            model = QueryModel.model_validate(col.query_model)
        query = fields.get("query", col.query) or ""
        col.query, col.query_model = _resolve_query(session, col.project_id, source_id, query, model)
        col.source_id = source_id
        col.last_error = None
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise Conflict("Сборщик с таким именем уже есть") from exc
    return col


def delete_collector(session: Session, user: AppUser, collector_id: int) -> None:
    col = get_collector(session, user, collector_id, "collector.manage")
    CollectorRepo(session).delete(col)
    session.commit()


def series_names(session: Session, user: AppUser, collector_id: int) -> list[str]:
    get_collector(session, user, collector_id)
    return SampleRepo(session).series_names(collector_id)


def run_collector(collector_id: int, now: datetime | None = None) -> dict:
    now = now or utcnow()
    with SessionLocal() as session:
        col = session.get(Collector, collector_id)
        if col is None:
            return {"values": {}, "error": "Сборщик не найден"}
        values: dict[str, float] = {}
        try:
            sql = time_macros.apply(col.query, now - timedelta(seconds=col.interval_sec), now, col.interval_sec)
            sql = query_guard.check(sql)
            result = connector.run_query(source_service.config_of(col.source), sql, max_rows=1000)
            for s in normalize(result.columns, result.rows).series:
                points = [p for p in s["points"] if p[1] is not None]
                if points:
                    values[s["name"][:200]] = float(points[-1][1])
            if not values:
                raise BadRequest("Запрос сборщика не вернул ни одного числового значения")
            session.add_all(Sample(collector_id=col.id, ts=now, series=k, value=v) for k, v in values.items())
            col.last_error = None
        except Exception as exc:
            col.last_error = str(getattr(exc, "message", None) or exc)[:2000]
            values = {}
        col.last_run_at = now
        events = alert_service.evaluate(session, col, values, now) if values else []
        project_id = col.project_id
        error = col.last_error
        session.commit()

    if values:
        bus.publish({"type": "sample", "collector_id": collector_id, "project_id": project_id, "ts": to_ms(now), "values": values})
    for event in events:
        bus.publish(event)
    return {"values": values, "error": error, "ts": to_ms(now)}

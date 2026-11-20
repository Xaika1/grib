from collections import OrderedDict
from datetime import datetime

from sqlalchemy.orm import Session

from app.core import executor, query_guard, time_macros
from app.core.connector import connector
from app.core.errors import BadRequest
from app.core.normalizer import normalize
from app.core.permissions import ensure
from app.core.timeutil import from_ms, parse_range, to_ms, utcnow
from app.models import AppUser, Collector, DataSource
from app.repositories import CollectorRepo, PanelRepo, SampleRepo, SourceRepo
from app.schemas.query import PreviewRequest
from app.services import source_service


def resolve_period(from_ms_: int | None, to_ms_: int | None, default_range: str = "6h") -> tuple[datetime, datetime]:
    t_to = from_ms(to_ms_) if to_ms_ else utcnow()
    t_from = from_ms(from_ms_) if from_ms_ else t_to - parse_range(default_range)
    if t_from >= t_to:
        raise BadRequest("Начало периода должно быть раньше конца")
    return t_from, t_to


def _source_in_project(session: Session, source_id: int | None, project_id: int) -> DataSource:
    if not source_id:
        raise BadRequest("Не выбран источник данных")
    src = SourceRepo(session).get_or_404(source_id)
    if src.project_id != project_id:
        raise BadRequest("Источник относится к другому проекту")
    return src


def _collector_in_project(session: Session, collector_id: int | None, project_id: int) -> Collector:
    if not collector_id:
        raise BadRequest("Не выбран сборщик")
    col = CollectorRepo(session).get_or_404(collector_id)
    if col.project_id != project_id:
        raise BadRequest("Сборщик относится к другому проекту")
    return col


async def _run_live(src: DataSource, sql: str, t_from: datetime, t_to: datetime) -> dict:
    prepared = query_guard.check(time_macros.apply(sql, t_from, t_to))
    cfg = source_service.config_of(src)
    result = await executor.run(connector.run_query, cfg, prepared)
    data = normalize(result.columns, result.rows).as_dict()
    data.update(truncated=result.truncated, elapsed_ms=result.elapsed_ms)
    return data


def _collector_data(session: Session, collector_id: int, t_from: datetime, t_to: datetime) -> dict:
    samples = SampleRepo(session).range(collector_id, t_from, t_to)
    series: OrderedDict[str, list] = OrderedDict()
    for s in samples:
        series.setdefault(s.series, []).append([to_ms(s.ts), s.value])
    last = {name: pts[-1] for name, pts in series.items()}
    return {
        "series": [{"name": n, "points": p} for n, p in series.items()],
        "table": {
            "columns": ["series", "time", "value"],
            "rows": [[n, from_ms(p[0]).isoformat() + "Z", p[1]] for n, p in last.items()],
        },
        "time_column": "time",
        "truncated": False,
        "elapsed_ms": 0,
    }


async def panel_data(session: Session, user: AppUser, panel_id: int, from_ms_: int | None, to_ms_: int | None) -> dict:
    panel = PanelRepo(session).get_or_404(panel_id)
    dashboard = panel.dashboard
    ensure(session, user, dashboard.project_id, "dashboard.view")
    t_from, t_to = resolve_period(from_ms_, to_ms_, dashboard.default_range)
    if panel.mode == "collector":
        _collector_in_project(session, panel.collector_id, dashboard.project_id)
        return _collector_data(session, panel.collector_id, t_from, t_to)
    src = _source_in_project(session, panel.source_id, dashboard.project_id)
    if not panel.query.strip():
        raise BadRequest("У панели не задан запрос")
    return await _run_live(src, panel.query, t_from, t_to)


async def preview(session: Session, user: AppUser, req: PreviewRequest) -> dict:
    t_from, t_to = resolve_period(req.from_ms, req.to_ms)
    if req.mode == "collector":
        ensure(session, user, req.project_id, "collector.view")
        _collector_in_project(session, req.collector_id, req.project_id)
        return _collector_data(session, req.collector_id, t_from, t_to)

    ensure(session, user, req.project_id, "query.run")
    src = _source_in_project(session, req.source_id, req.project_id)
    if req.query_model is not None:
        sql = await executor.run(source_service.build_for_source, src, req.query_model)
    else:
        sql = req.query
    if not sql.strip():
        raise BadRequest("Пустой запрос")
    data = await _run_live(src, sql, t_from, t_to)
    data["sql"] = sql
    return data

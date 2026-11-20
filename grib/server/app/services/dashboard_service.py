from typing import Any

from sqlalchemy.orm import Session

from app.core import query_guard, time_macros
from app.core.errors import BadRequest, Conflict
from app.core.event_bus import bus
from app.core.permissions import ensure
from app.core.timeutil import utcnow
from app.models import AppUser, Dashboard, Panel
from app.repositories import CollectorRepo, DashboardRepo, PanelRepo, ProjectRepo, SourceRepo
from app.schemas.monitoring import (
    DashboardCreate,
    DashboardImport,
    DashboardUpdate,
    PanelCreate,
    PanelUpdate,
)
from app.schemas.query import QueryModel
from app.services import source_service

EXPORT_VERSION = 1


def get_dashboard(session: Session, user: AppUser, dashboard_id: int, permission: str = "dashboard.view") -> Dashboard:
    dash = DashboardRepo(session).get_or_404(dashboard_id)
    ensure(session, user, dash.project_id, permission)
    return dash


def list_dashboards(session: Session, user: AppUser, project_id: int) -> list[Dashboard]:
    ensure(session, user, project_id, "dashboard.view")
    return DashboardRepo(session).for_project(project_id)


def create_dashboard(session: Session, user: AppUser, project_id: int, data: DashboardCreate) -> Dashboard:
    ensure(session, user, project_id, "dashboard.edit")
    ProjectRepo(session).get_or_404(project_id)
    dash = DashboardRepo(session).add(Dashboard(project_id=project_id, **data.model_dump()))
    session.commit()
    return dash


def update_dashboard(session: Session, user: AppUser, dashboard_id: int, data: DashboardUpdate) -> Dashboard:
    dash = get_dashboard(session, user, dashboard_id, "dashboard.edit")
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(dash, key, value)
    session.commit()
    return dash


def delete_dashboard(session: Session, user: AppUser, dashboard_id: int) -> None:
    dash = get_dashboard(session, user, dashboard_id, "dashboard.edit")
    DashboardRepo(session).delete(dash)
    session.commit()


def subscription_collectors(session: Session, user: AppUser, dashboard_id: int) -> set[int]:
    get_dashboard(session, user, dashboard_id)
    return PanelRepo(session).collector_ids(dashboard_id)


def _touch(session: Session, dash: Dashboard) -> None:
    dash.updated_at = utcnow()
    session.commit()
    bus.refresh_dashboard(dash.id, PanelRepo(session).collector_ids(dash.id))


def _apply_panel(session: Session, project_id: int, panel: Panel, fields: dict[str, Any], model: QueryModel | None, clear_model: bool) -> None:
    for key in ("title", "type", "mode", "grid_w", "grid_h", "position"):
        if fields.get(key) is not None:
            setattr(panel, key, fields[key])
    for key in ("source_id", "collector_id"):
        if key in fields:
            setattr(panel, key, fields[key])
    settings = dict(panel.settings or {})
    if fields.get("settings") is not None:
        keep_model = settings.get("query_model")
        settings = dict(fields["settings"])
        settings.pop("query_model", None)
        if keep_model is not None:
            settings["query_model"] = keep_model
    if "query" in fields and fields["query"] is not None:
        panel.query = fields["query"]
        if model is None:
            settings.pop("query_model", None)
    if clear_model:
        settings.pop("query_model", None)

    if panel.mode == "collector":
        if not panel.collector_id:
            raise BadRequest("Выберите сборщик для панели")
        col = CollectorRepo(session).get_or_404(panel.collector_id)
        if col.project_id != project_id:
            raise BadRequest("Сборщик относится к другому проекту")
    else:
        if not panel.source_id:
            raise BadRequest("Выберите источник данных для панели")
        src = SourceRepo(session).get_or_404(panel.source_id)
        if src.project_id != project_id:
            raise BadRequest("Источник относится к другому проекту")
        if model is not None:
            panel.query = source_service.build_for_source(src, model)
            settings["query_model"] = model.model_dump()
        if not panel.query.strip():
            raise BadRequest("Задайте запрос панели")
        now = utcnow()
        query_guard.check(time_macros.apply(panel.query, now, now))
    panel.settings = settings


def create_panel(session: Session, user: AppUser, dashboard_id: int, data: PanelCreate) -> Panel:
    dash = get_dashboard(session, user, dashboard_id, "dashboard.edit")
    if data.mode == "live":
        ensure(session, user, dash.project_id, "query.run")
    repo = PanelRepo(session)
    panel = Panel(dashboard_id=dash.id, settings={}, query="")
    fields = data.model_dump(exclude={"query_model"})
    if fields.get("position") is None:
        fields["position"] = repo.next_position(dash.id)
    _apply_panel(session, dash.project_id, panel, fields, data.query_model, False)
    repo.add(panel)
    _touch(session, dash)
    return panel


def update_panel(session: Session, user: AppUser, panel_id: int, data: PanelUpdate) -> Panel:
    panel = PanelRepo(session).get_or_404(panel_id)
    dash = get_dashboard(session, user, panel.dashboard_id, "dashboard.edit")
    fields = data.model_dump(exclude_unset=True, exclude={"query_model", "clear_query_model"})
    query_changed = data.query_model is not None or "query" in fields or "source_id" in fields
    if query_changed and (fields.get("mode") or panel.mode) == "live":
        ensure(session, user, dash.project_id, "query.run")
    _apply_panel(session, dash.project_id, panel, fields, data.query_model, data.clear_query_model)
    _touch(session, dash)
    return panel


def delete_panel(session: Session, user: AppUser, panel_id: int) -> None:
    panel = PanelRepo(session).get_or_404(panel_id)
    dash = get_dashboard(session, user, panel.dashboard_id, "dashboard.edit")
    PanelRepo(session).delete(panel)
    _touch(session, dash)


def reorder_panels(session: Session, user: AppUser, dashboard_id: int, panel_ids: list[int]) -> Dashboard:
    dash = get_dashboard(session, user, dashboard_id, "dashboard.edit")
    by_id = {p.id: p for p in dash.panels}
    if set(panel_ids) != set(by_id):
        raise BadRequest("Список панелей не совпадает с панелями дашборда")
    for position, pid in enumerate(panel_ids):
        by_id[pid].position = position
    _touch(session, dash)
    session.refresh(dash)
    return dash


def export_dashboard(session: Session, user: AppUser, dashboard_id: int) -> dict:
    dash = get_dashboard(session, user, dashboard_id)
    return {
        "grib_export": EXPORT_VERSION,
        "dashboard": {
            "title": dash.title,
            "description": dash.description,
            "default_range": dash.default_range,
            "refresh_sec": dash.refresh_sec,
        },
        "panels": [
            {
                "title": p.title,
                "type": p.type,
                "mode": p.mode,
                "source": p.source.name if p.source else None,
                "collector": p.collector.name if p.collector else None,
                "query": p.query,
                "settings": p.settings or {},
                "grid_w": p.grid_w,
                "grid_h": p.grid_h,
                "position": p.position,
            }
            for p in dash.panels
        ],
    }


def import_dashboard(session: Session, user: AppUser, project_id: int, req: DashboardImport) -> Dashboard:
    ensure(session, user, project_id, "dashboard.edit")
    data = req.data
    if not isinstance(data, dict) or data.get("grib_export") != EXPORT_VERSION or not isinstance(data.get("dashboard"), dict):
        raise BadRequest("Файл не похож на экспорт дашборда «Гриба»")
    panels = data.get("panels") or []
    if not isinstance(panels, list):
        raise BadRequest("Неверный формат списка панелей")

    sources = SourceRepo(session)
    collectors = CollectorRepo(session)
    missing_sources, missing_collectors = set(), set()
    source_ids: dict[str, int] = {}
    collector_ids: dict[str, int] = {}
    for p in panels:
        if not isinstance(p, dict):
            raise BadRequest("Неверный формат панели")
        name = p.get("source")
        if p.get("mode", "live") == "live" and name:
            if name in req.source_map:
                src = sources.get(req.source_map[name])
                if src is None or src.project_id != project_id:
                    raise BadRequest(f"Неверная замена для источника «{name}»")
                source_ids[name] = src.id
            elif (src := sources.by_name(project_id, name)) is not None:
                source_ids[name] = src.id
            else:
                missing_sources.add(name)
        cname = p.get("collector")
        if p.get("mode") == "collector" and cname:
            if cname in req.collector_map:
                col = collectors.get(req.collector_map[cname])
                if col is None or col.project_id != project_id:
                    raise BadRequest(f"Неверная замена для сборщика «{cname}»")
                collector_ids[cname] = col.id
            elif (col := collectors.by_name(project_id, cname)) is not None:
                collector_ids[cname] = col.id
            else:
                missing_collectors.add(cname)
    if missing_sources or missing_collectors:
        raise Conflict(
            "В проекте нет некоторых источников или сборщиков. Выберите замену",
            {"missing_sources": sorted(missing_sources), "missing_collectors": sorted(missing_collectors)},
        )

    meta = data["dashboard"]
    dash_data = DashboardCreate.model_validate(
        {
            "title": req.title or meta.get("title") or "Импортированный дашборд",
            "description": meta.get("description") or "",
            "default_range": meta.get("default_range") or "6h",
            "refresh_sec": meta.get("refresh_sec", 30),
        }
    )
    dash = DashboardRepo(session).add(Dashboard(project_id=project_id, **dash_data.model_dump()))
    for i, p in enumerate(panels):
        spec = PanelCreate.model_validate(
            {
                "title": p.get("title") or "",
                "type": p.get("type") or "line",
                "mode": p.get("mode") or "live",
                "source_id": source_ids.get(p.get("source") or ""),
                "collector_id": collector_ids.get(p.get("collector") or ""),
                "query": p.get("query") or "",
                "settings": p.get("settings") or {},
                "grid_w": p.get("grid_w") or 6,
                "grid_h": p.get("grid_h") or 1,
                "position": p.get("position", i),
            }
        )
        panel = Panel(dashboard_id=dash.id, settings={}, query="")
        _apply_panel(session, project_id, panel, spec.model_dump(exclude={"query_model"}), None, False)
        panel.settings = dict(spec.settings)
        session.add(panel)
    session.commit()
    session.refresh(dash)
    return dash

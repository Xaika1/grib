from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.models import AppUser
from app.routers.deps import current_user, get_db
from app.schemas.monitoring import (
    DashboardCreate,
    DashboardFull,
    DashboardImport,
    DashboardOut,
    DashboardUpdate,
    PanelCreate,
    PanelOrder,
    PanelOut,
    PanelUpdate,
)
from app.services import dashboard_service, query_service

router = APIRouter(tags=["dashboards"])


@router.get("/projects/{project_id}/dashboards", response_model=list[DashboardOut])
def dashboards(project_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return dashboard_service.list_dashboards(session, user, project_id)


@router.post("/projects/{project_id}/dashboards", response_model=DashboardFull, status_code=201)
def create_dashboard(project_id: int, data: DashboardCreate, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return dashboard_service.create_dashboard(session, user, project_id, data)


@router.post("/projects/{project_id}/dashboards/import", response_model=DashboardFull, status_code=201)
def import_dashboard(project_id: int, data: DashboardImport, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return dashboard_service.import_dashboard(session, user, project_id, data)


@router.get("/dashboards/{dashboard_id}", response_model=DashboardFull)
def dashboard(dashboard_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return dashboard_service.get_dashboard(session, user, dashboard_id)


@router.patch("/dashboards/{dashboard_id}", response_model=DashboardFull)
def update_dashboard(dashboard_id: int, data: DashboardUpdate, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return dashboard_service.update_dashboard(session, user, dashboard_id, data)


@router.delete("/dashboards/{dashboard_id}", status_code=204)
def delete_dashboard(dashboard_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    dashboard_service.delete_dashboard(session, user, dashboard_id)
    return Response(status_code=204)


@router.get("/dashboards/{dashboard_id}/export")
def export_dashboard(dashboard_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return dashboard_service.export_dashboard(session, user, dashboard_id)


@router.put("/dashboards/{dashboard_id}/order", response_model=DashboardFull)
def reorder(dashboard_id: int, data: PanelOrder, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return dashboard_service.reorder_panels(session, user, dashboard_id, data.panel_ids)


@router.post("/dashboards/{dashboard_id}/panels", response_model=PanelOut, status_code=201)
def create_panel(dashboard_id: int, data: PanelCreate, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return dashboard_service.create_panel(session, user, dashboard_id, data)


@router.patch("/panels/{panel_id}", response_model=PanelOut)
def update_panel(panel_id: int, data: PanelUpdate, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return dashboard_service.update_panel(session, user, panel_id, data)


@router.delete("/panels/{panel_id}", status_code=204)
def delete_panel(panel_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    dashboard_service.delete_panel(session, user, panel_id)
    return Response(status_code=204)


@router.get("/panels/{panel_id}/data")
async def panel_data(
    panel_id: int,
    from_ms: int | None = None,
    to_ms: int | None = None,
    user: AppUser = Depends(current_user),
    session: Session = Depends(get_db),
):
    return await query_service.panel_data(session, user, panel_id, from_ms, to_ms)

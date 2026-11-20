from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core import executor
from app.models import AppUser
from app.routers.deps import current_user, get_db
from app.schemas.monitoring import (
    AlertEventOut,
    AlertRuleCreate,
    AlertRuleOut,
    AlertRuleUpdate,
    CollectorCreate,
    CollectorOut,
    CollectorUpdate,
)
from app.services import alert_service, collector_service

router = APIRouter(tags=["collectors", "alerts"])


@router.get("/projects/{project_id}/collectors", response_model=list[CollectorOut])
def collectors(project_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return collector_service.list_collectors(session, user, project_id)


@router.post("/projects/{project_id}/collectors", response_model=CollectorOut, status_code=201)
def create_collector(project_id: int, data: CollectorCreate, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return collector_service.create_collector(session, user, project_id, data)


@router.get("/collectors/{collector_id}", response_model=CollectorOut)
def collector(collector_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return collector_service.get_collector(session, user, collector_id)


@router.patch("/collectors/{collector_id}", response_model=CollectorOut)
def update_collector(collector_id: int, data: CollectorUpdate, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return collector_service.update_collector(session, user, collector_id, data)


@router.delete("/collectors/{collector_id}", status_code=204)
def delete_collector(collector_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    collector_service.delete_collector(session, user, collector_id)
    return Response(status_code=204)


@router.post("/collectors/{collector_id}/run")
async def run_collector(collector_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    collector_service.get_collector(session, user, collector_id, "collector.manage")
    return await executor.run(collector_service.run_collector, collector_id)


@router.get("/collectors/{collector_id}/series", response_model=list[str])
def collector_series(collector_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return collector_service.series_names(session, user, collector_id)


@router.get("/projects/{project_id}/alerts", response_model=list[AlertRuleOut])
def alert_rules(project_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return alert_service.list_rules(session, user, project_id)


@router.post("/projects/{project_id}/alerts", response_model=AlertRuleOut, status_code=201)
def create_alert_rule(project_id: int, data: AlertRuleCreate, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return alert_service.create_rule(session, user, project_id, data)


@router.patch("/alerts/{rule_id}", response_model=AlertRuleOut)
def update_alert_rule(rule_id: int, data: AlertRuleUpdate, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return alert_service.update_rule(session, user, rule_id, data)


@router.delete("/alerts/{rule_id}", status_code=204)
def delete_alert_rule(rule_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    alert_service.delete_rule(session, user, rule_id)
    return Response(status_code=204)


@router.get("/projects/{project_id}/alert-events", response_model=list[AlertEventOut])
def alert_events(project_id: int, limit: int = 100, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return alert_service.project_events(session, user, project_id, min(max(limit, 1), 500))


@router.get("/alert-events/active", response_model=list[AlertEventOut])
def active_alert_events(user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return alert_service.active_events(session, user)

import operator
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errors import BadRequest
from app.core.permissions import ensure, user_permissions
from app.core.timeutil import to_ms
from app.models import AlertEvent, AlertRule, AppUser, Collector
from app.repositories import AlertEventRepo, AlertRuleRepo, CollectorRepo, MemberRepo, ProjectRepo
from app.schemas.monitoring import AlertEventOut, AlertRuleCreate, AlertRuleUpdate

OPS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le, "==": operator.eq, "!=": operator.ne}


def evaluate(session: Session, collector: Collector, values: dict[str, float], now: datetime) -> list[dict]:
    out: list[dict] = []
    events = AlertEventRepo(session)
    for rule in AlertRuleRepo(session).for_collector(collector.id, only_enabled=True):
        if rule.series:
            value = values.get(rule.series)
        else:
            value = next(iter(values.values()), None)
        if value is None:
            continue
        rule.last_value = value
        rule.last_eval_at = now
        previous = rule.state
        event: AlertEvent | None = None

        if OPS[rule.operator](value, rule.threshold):
            if rule.state == "ok":
                rule.state = "pending"
                rule.pending_since = now
            if rule.state == "pending" and (now - (rule.pending_since or now)).total_seconds() >= rule.for_sec:
                rule.state = "firing"
                event = AlertEvent(
                    rule_id=rule.id,
                    started_at=now,
                    value=value,
                    message=f"{rule.name}: {rule.series or 'значение'} = {value:g} ({rule.operator} {rule.threshold:g})",
                )
                events.add(event)
        else:
            if rule.state == "firing":
                event = events.open_for_rule(rule.id)
                if event is not None:
                    event.ended_at = now
            rule.state = "ok"
            rule.pending_since = None

        if rule.state != previous:
            out.append(
                {
                    "type": "alert",
                    "project_id": collector.project_id,
                    "rule_id": rule.id,
                    "name": rule.name,
                    "state": rule.state,
                    "previous": previous,
                    "value": value,
                    "threshold": rule.threshold,
                    "operator": rule.operator,
                    "ts": to_ms(now),
                    "event_id": event.id if event is not None else None,
                    "message": event.message if event is not None else "",
                }
            )
    session.flush()
    return out


def _rule(session: Session, user: AppUser, rule_id: int, permission: str) -> AlertRule:
    rule = AlertRuleRepo(session).get_or_404(rule_id)
    ensure(session, user, rule.collector.project_id, permission)
    return rule


def list_rules(session: Session, user: AppUser, project_id: int) -> list[AlertRule]:
    ensure(session, user, project_id, "alert.view")
    return AlertRuleRepo(session).for_project(project_id)


def create_rule(session: Session, user: AppUser, project_id: int, data: AlertRuleCreate) -> AlertRule:
    ensure(session, user, project_id, "alert.manage")
    collector = CollectorRepo(session).get_or_404(data.collector_id)
    if collector.project_id != project_id:
        raise BadRequest("Сборщик относится к другому проекту")
    rule = AlertRuleRepo(session).add(AlertRule(**data.model_dump()))
    session.commit()
    return rule


def update_rule(session: Session, user: AppUser, rule_id: int, data: AlertRuleUpdate) -> AlertRule:
    rule = _rule(session, user, rule_id, "alert.manage")
    fields = data.model_dump(exclude_unset=True)
    condition_changed = any(k in fields for k in ("series", "operator", "threshold", "for_sec", "enabled"))
    for key, value in fields.items():
        if value is not None or key == "series":
            setattr(rule, key, value)
    if condition_changed and rule.state != "ok":
        open_event = AlertEventRepo(session).open_for_rule(rule.id)
        if open_event is not None and rule.last_eval_at is not None:
            open_event.ended_at = rule.last_eval_at
        rule.state, rule.pending_since = "ok", None
    session.commit()
    return rule


def delete_rule(session: Session, user: AppUser, rule_id: int) -> None:
    rule = _rule(session, user, rule_id, "alert.manage")
    AlertRuleRepo(session).delete(rule)
    session.commit()


def _event_out(e: AlertEvent) -> AlertEventOut:
    return AlertEventOut(
        id=e.id,
        rule_id=e.rule_id,
        rule_name=e.rule.name,
        project_id=e.rule.collector.project_id,
        started_at=e.started_at,
        ended_at=e.ended_at,
        value=e.value,
        message=e.message,
    )


def alert_projects(session: Session, user: AppUser) -> list[int] | None:
    if user.is_admin:
        return None
    return [m.project_id for m in MemberRepo(session).for_user(user.id) if "alert.view" in m.role.codes]


def project_events(session: Session, user: AppUser, project_id: int, limit: int = 100) -> list[AlertEventOut]:
    ensure(session, user, project_id, "alert.view")
    ProjectRepo(session).get_or_404(project_id)
    return [_event_out(e) for e in AlertEventRepo(session).feed([project_id], limit=limit)]


def active_events(session: Session, user: AppUser) -> list[AlertEventOut]:
    projects = alert_projects(session, user)
    return [_event_out(e) for e in AlertEventRepo(session).feed(projects, limit=200, only_active=True)]


def can_view(session: Session, user: AppUser, project_id: int) -> bool:
    return "alert.view" in user_permissions(session, user, project_id)

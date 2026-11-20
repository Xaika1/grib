from datetime import datetime
from typing import Generic, TypeVar

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.models import (
    AlertEvent,
    AlertRule,
    AppUser,
    Collector,
    Dashboard,
    DataSource,
    Panel,
    Permission,
    Project,
    ProjectMember,
    Role,
    Sample,
)

T = TypeVar("T")


class Repository(Generic[T]):
    model: type
    title = "Объект"

    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, obj_id: int) -> T | None:
        return self.s.get(self.model, obj_id)

    def get_or_404(self, obj_id: int) -> T:
        obj = self.get(obj_id)
        if obj is None:
            raise NotFound(f"{self.title} не найден(а)")
        return obj

    def add(self, obj: T) -> T:
        self.s.add(obj)
        self.s.flush()
        return obj

    def delete(self, obj: T) -> None:
        self.s.delete(obj)
        self.s.flush()


class UserRepo(Repository[AppUser]):
    model, title = AppUser, "Пользователь"

    def by_login(self, login: str) -> AppUser | None:
        return self.s.scalar(select(AppUser).where(func.lower(AppUser.login) == login.lower()))

    def search(self, q: str = "") -> list[AppUser]:
        stmt = select(AppUser).order_by(AppUser.login)
        if q:
            like = f"%{q.lower()}%"
            stmt = stmt.where(or_(func.lower(AppUser.login).like(like), func.lower(AppUser.full_name).like(like)))
        return list(self.s.scalars(stmt))

    def count(self) -> int:
        return self.s.scalar(select(func.count()).select_from(AppUser)) or 0

    def count_admins(self) -> int:
        return (
            self.s.scalar(
                select(func.count()).select_from(AppUser).where(AppUser.is_admin.is_(True), AppUser.is_blocked.is_(False))
            )
            or 0
        )


class PermissionRepo(Repository[Permission]):
    model, title = Permission, "Право"

    def all(self) -> list[Permission]:
        return list(self.s.scalars(select(Permission).order_by(Permission.code)))


class RoleRepo(Repository[Role]):
    model, title = Role, "Роль"

    def all(self) -> list[Role]:
        return list(self.s.scalars(select(Role).order_by(Role.is_builtin.desc(), Role.id)))

    def by_name(self, name: str) -> Role | None:
        return self.s.scalar(select(Role).where(Role.name == name))

    def member_counts(self) -> dict[int, int]:
        rows = self.s.execute(select(ProjectMember.role_id, func.count()).group_by(ProjectMember.role_id))
        return {role_id: n for role_id, n in rows}


class ProjectRepo(Repository[Project]):
    model, title = Project, "Проект"

    def by_name(self, name: str) -> Project | None:
        return self.s.scalar(select(Project).where(Project.name == name))

    def visible_for(self, user: AppUser) -> list[Project]:
        stmt = select(Project).order_by(Project.name)
        if not user.is_admin:
            stmt = stmt.join(ProjectMember, ProjectMember.project_id == Project.id).where(
                ProjectMember.user_id == user.id
            )
        return list(self.s.scalars(stmt))

    def counts(self, project_id: int) -> dict[str, int]:
        def n(model) -> int:
            return self.s.scalar(select(func.count()).select_from(model).where(model.project_id == project_id)) or 0

        return {
            "dashboards": n(Dashboard),
            "sources": n(DataSource),
            "collectors": n(Collector),
            "members": n(ProjectMember),
        }


class MemberRepo(Repository[ProjectMember]):
    model, title = ProjectMember, "Участник"

    def for_project(self, project_id: int) -> list[ProjectMember]:
        stmt = (
            select(ProjectMember)
            .join(AppUser, AppUser.id == ProjectMember.user_id)
            .where(ProjectMember.project_id == project_id)
            .order_by(AppUser.login)
        )
        return list(self.s.scalars(stmt))

    def find(self, project_id: int, user_id: int) -> ProjectMember | None:
        return self.s.scalar(
            select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        )

    def for_user(self, user_id: int) -> list[ProjectMember]:
        return list(self.s.scalars(select(ProjectMember).where(ProjectMember.user_id == user_id)))

    def count_role(self, project_id: int, role_id: int) -> int:
        return (
            self.s.scalar(
                select(func.count())
                .select_from(ProjectMember)
                .where(ProjectMember.project_id == project_id, ProjectMember.role_id == role_id)
            )
            or 0
        )


class SourceRepo(Repository[DataSource]):
    model, title = DataSource, "Источник данных"

    def for_project(self, project_id: int) -> list[DataSource]:
        return list(
            self.s.scalars(select(DataSource).where(DataSource.project_id == project_id).order_by(DataSource.name))
        )

    def by_name(self, project_id: int, name: str) -> DataSource | None:
        return self.s.scalar(select(DataSource).where(DataSource.project_id == project_id, DataSource.name == name))


class DashboardRepo(Repository[Dashboard]):
    model, title = Dashboard, "Дашборд"

    def for_project(self, project_id: int) -> list[Dashboard]:
        return list(
            self.s.scalars(select(Dashboard).where(Dashboard.project_id == project_id).order_by(Dashboard.title))
        )


class PanelRepo(Repository[Panel]):
    model, title = Panel, "Панель"

    def collector_ids(self, dashboard_id: int) -> set[int]:
        rows = self.s.scalars(
            select(Panel.collector_id).where(
                Panel.dashboard_id == dashboard_id, Panel.mode == "collector", Panel.collector_id.is_not(None)
            )
        )
        return set(rows)

    def next_position(self, dashboard_id: int) -> int:
        current = self.s.scalar(select(func.max(Panel.position)).where(Panel.dashboard_id == dashboard_id))
        return (current or 0) + 1 if current is not None else 0


class CollectorRepo(Repository[Collector]):
    model, title = Collector, "Сборщик"

    def for_project(self, project_id: int) -> list[Collector]:
        return list(
            self.s.scalars(select(Collector).where(Collector.project_id == project_id).order_by(Collector.name))
        )

    def by_name(self, project_id: int, name: str) -> Collector | None:
        return self.s.scalar(select(Collector).where(Collector.project_id == project_id, Collector.name == name))


class SampleRepo(Repository[Sample]):
    model, title = Sample, "Замер"

    def range(self, collector_id: int, t_from: datetime, t_to: datetime, limit: int = 20_000) -> list[Sample]:
        stmt = (
            select(Sample)
            .where(Sample.collector_id == collector_id, Sample.ts >= t_from, Sample.ts <= t_to)
            .order_by(Sample.ts.desc())
            .limit(limit)
        )
        return list(reversed(list(self.s.scalars(stmt))))

    def series_names(self, collector_id: int) -> list[str]:
        stmt = select(Sample.series).where(Sample.collector_id == collector_id).distinct().order_by(Sample.series)
        return list(self.s.scalars(stmt))

    def latest(self, collector_id: int) -> list[Sample]:
        last_ts = self.s.scalar(select(func.max(Sample.ts)).where(Sample.collector_id == collector_id))
        if last_ts is None:
            return []
        return list(self.s.scalars(select(Sample).where(Sample.collector_id == collector_id, Sample.ts == last_ts)))


class AlertRuleRepo(Repository[AlertRule]):
    model, title = AlertRule, "Правило алерта"

    def for_collector(self, collector_id: int, only_enabled: bool = False) -> list[AlertRule]:
        stmt = select(AlertRule).where(AlertRule.collector_id == collector_id)
        if only_enabled:
            stmt = stmt.where(AlertRule.enabled.is_(True))
        return list(self.s.scalars(stmt.order_by(AlertRule.id)))

    def for_project(self, project_id: int) -> list[AlertRule]:
        stmt = (
            select(AlertRule)
            .join(Collector, Collector.id == AlertRule.collector_id)
            .where(Collector.project_id == project_id)
            .order_by(AlertRule.name)
        )
        return list(self.s.scalars(stmt))


class AlertEventRepo(Repository[AlertEvent]):
    model, title = AlertEvent, "Событие алерта"

    def open_for_rule(self, rule_id: int) -> AlertEvent | None:
        return self.s.scalar(
            select(AlertEvent)
            .where(AlertEvent.rule_id == rule_id, AlertEvent.ended_at.is_(None))
            .order_by(AlertEvent.id.desc())
        )

    def feed(self, project_ids: list[int] | None, limit: int = 100, only_active: bool = False) -> list[AlertEvent]:
        stmt = (
            select(AlertEvent)
            .join(AlertRule, AlertRule.id == AlertEvent.rule_id)
            .join(Collector, Collector.id == AlertRule.collector_id)
        )
        if project_ids is not None:
            stmt = stmt.where(Collector.project_id.in_(project_ids))
        if only_active:
            stmt = stmt.where(AlertEvent.ended_at.is_(None))
        return list(self.s.scalars(stmt.order_by(AlertEvent.started_at.desc(), AlertEvent.id.desc()).limit(limit)))

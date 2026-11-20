from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Forbidden
from app.models import AppUser, ProjectMember

PERMISSIONS: dict[str, str] = {
    "project.manage": "Изменение и удаление проекта",
    "project.members": "Управление участниками проекта",
    "source.view": "Просмотр источников данных",
    "source.manage": "Создание, изменение и удаление источников данных",
    "dashboard.view": "Просмотр дашбордов",
    "dashboard.edit": "Создание и изменение дашбордов и панелей",
    "query.run": "Выполнение произвольных запросов к источникам (редактор панели, билдер)",
    "collector.view": "Просмотр сборщиков",
    "collector.manage": "Создание, изменение и запуск сборщиков",
    "alert.view": "Просмотр алертов и получение уведомлений",
    "alert.manage": "Создание и изменение правил алертов",
}

OWNER_ROLE = "Владелец проекта"
EDITOR_ROLE = "Редактор"
VIEWER_ROLE = "Наблюдатель"

BUILTIN_ROLES: dict[str, tuple[str, set[str]]] = {
    OWNER_ROLE: ("Полный доступ к проекту", set(PERMISSIONS)),
    EDITOR_ROLE: (
        "Создаёт и меняет дашборды, панели и запросы",
        {"dashboard.view", "dashboard.edit", "query.run", "source.view", "collector.view", "alert.view"},
    ),
    VIEWER_ROLE: ("Только просмотр дашбордов и уведомления", {"dashboard.view", "collector.view", "alert.view"}),
}


def user_permissions(session: Session, user: AppUser, project_id: int) -> set[str]:
    if user.is_admin:
        return set(PERMISSIONS)
    member = session.scalar(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
    )
    return member.role.codes if member else set()


def ensure(session: Session, user: AppUser, project_id: int, permission: str) -> None:
    if permission not in user_permissions(session, user, project_id):
        title = PERMISSIONS.get(permission, permission)
        raise Forbidden(f"Недостаточно прав: {title.lower()} ({permission})")


def ensure_admin(user: AppUser) -> None:
    if not user.is_admin:
        raise Forbidden("Действие доступно только администратору системы")
